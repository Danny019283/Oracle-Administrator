import re

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.dependencias import obtener_entorno
from src.api.respaldos import obtener_consulta
from src.api.sesion import obtener_almacen
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones
from tests.services.entorno_falso import EntornoFalso

ALMACEN = AlmacenSesiones()
TOKEN = ALMACEN.crear(Conexion(usuario="SYSTEM", password="s3creta!", servicio="XEPDB1"))
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
RUTA = "/opt/oracle/Respaldos"
SOLICITUD = {"schemas": ["HR"], "directorio": "RESPALDO", "nombre": "ventas"}


class ConsultaFalsa:
    def __init__(self, schemas=(("HR",), ("VENTAS",)), directorios=(("RESPALDO", RUTA),)):
        self.schemas = list(schemas)
        self.directorios = list(directorios)

    def __call__(self, sql, params=None):
        return self.schemas if "all_users" in sql.lower() else self.directorios


LOG_DUPLICADO = "ORA-27038: el archivo creado ya existe"


@pytest.fixture
def cliente():
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(consulta=None, entorno=None):
    consulta = consulta or ConsultaFalsa()
    entorno = entorno or EntornoFalso(log=LOG_DUPLICADO)
    app.dependency_overrides[obtener_consulta] = lambda: consulta
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    return entorno


def test_lista_los_schemas_de_usuario(cliente):
    usar()

    respuesta = cliente.get("/respaldos/schemas", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"schemas": ["HR", "VENTAS"]}


def test_sin_schemas_responde_404_con_el_mensaje(cliente):
    usar(consulta=ConsultaFalsa(schemas=[]))

    respuesta = cliente.get("/respaldos/schemas", headers=CABECERAS)

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "No hay schemas de usuario"


def test_respalda_y_devuelve_los_nombres_del_dmp_y_del_log(cliente):
    entorno = usar()

    respuesta = cliente.post("/respaldos/schemas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert re.fullmatch(r"ventas_\d{8}_\d{6}\.dmp", cuerpo["dmp"])
    assert cuerpo["log"] == cuerpo["dmp"].replace(".dmp", ".log")
    assert "s3creta!" not in respuesta.text

    (herramienta,) = entorno.herramientas
    assert herramienta["nombre"] == "expdp"
    assert "SCHEMAS=HR" in herramienta["script"].splitlines()


def test_solicitud_invalida_responde_422_con_todos_los_errores_y_no_ejecuta_expdp(cliente):
    entorno = usar()
    solicitud = {"schemas": [], "directorio": "OTRO", "nombre": ""}

    respuesta = cliente.post("/respaldos/schemas", json=solicitud, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        "Debes seleccionar al menos un schema",
        "El directorio OTRO no está disponible",
        "Debes ingresar un nombre de dumpfile",
    ]
    assert entorno.herramientas == []


def test_sin_directorios_la_solicitud_se_rechaza_con_422(cliente):
    entorno = usar(consulta=ConsultaFalsa(directorios=[]))

    respuesta = cliente.post("/respaldos/schemas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert "El directorio RESPALDO no está disponible" in respuesta.json()["errores"]
    assert entorno.herramientas == []


def test_si_expdp_falla_responde_500_con_mensaje_explicacion_y_log(cliente):
    entorno = usar(entorno=EntornoFalso(codigo=5, log=LOG_DUPLICADO))

    respuesta = cliente.post("/respaldos/schemas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert "terminó con código 5" in cuerpo["mensaje"]
    assert cuerpo["explicacion"] == "Ya existe un archivo de respaldo con ese nombre en el directorio"
    assert "ORA-27038" in cuerpo["log"]
    assert "s3creta!" not in respuesta.text
    assert str(entorno.lecturas[0]).startswith(f"{RUTA}/ventas_")
