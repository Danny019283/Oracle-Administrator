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
TOKEN = ALMACEN.crear(Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1"))
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
RUTA = "/opt/oracle/Respaldos"
SOLICITUD = {"tablas": ["CLIENTES"], "directorio": "RESPALDO", "nombre": "ventas"}


class ConsultaFalsa:
    def __init__(self, tablas=(("CLIENTES",), ("PEDIDOS",)), directorios=(("RESPALDO", RUTA),)):
        self.tablas = list(tablas)
        self.directorios = list(directorios)

    def __call__(self, sql, params=None):
        return self.tablas if "user_tables" in sql.lower() else self.directorios


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


def test_lista_las_tablas_del_usuario(cliente):
    usar()

    respuesta = cliente.get("/respaldos/tablas", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tablas": ["CLIENTES", "PEDIDOS"]}


def test_sin_tablas_responde_404_con_el_mensaje(cliente):
    usar(consulta=ConsultaFalsa(tablas=[]))

    respuesta = cliente.get("/respaldos/tablas", headers=CABECERAS)

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "No hay tablas en el schema"


def test_lista_los_directorios_con_nombre_y_ruta(cliente):
    usar()

    respuesta = cliente.get("/respaldos/directorios", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"directorios": [{"nombre": "RESPALDO", "ruta": RUTA}]}


def test_sin_directorios_responde_404_y_sugiere_crear_uno(cliente):
    usar(consulta=ConsultaFalsa(directorios=[]))

    respuesta = cliente.get("/respaldos/directorios", headers=CABECERAS)

    assert respuesta.status_code == 404
    assert "No hay directorios disponibles" in respuesta.json()["detail"]
    assert "crear" in respuesta.json()["detail"]


def test_respalda_y_devuelve_los_nombres_del_dmp_y_del_log(cliente):
    entorno = usar()

    respuesta = cliente.post("/respaldos/tablas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert re.fullmatch(r"ventas_\d{8}_\d{6}\.dmp", cuerpo["dmp"])
    assert cuerpo["log"] == cuerpo["dmp"].replace(".dmp", ".log")
    assert "s3creta!" not in respuesta.text

    (herramienta,) = entorno.herramientas
    assert herramienta["nombre"] == "expdp"
    parfile = herramienta["script"].splitlines()
    assert "USERID=HR/s3creta!@XEPDB1" in parfile
    assert "TABLES=CLIENTES" in parfile


def test_solicitud_invalida_responde_422_con_todos_los_errores_y_no_ejecuta_expdp(cliente):
    entorno = usar()
    solicitud = {"tablas": [], "directorio": "OTRO", "nombre": ""}

    respuesta = cliente.post("/respaldos/tablas", json=solicitud, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        "Debes seleccionar al menos una tabla",
        "El directorio OTRO no está disponible",
        "Debes ingresar un nombre de dumpfile",
    ]
    assert entorno.herramientas == []


def test_si_expdp_falla_responde_500_con_el_mensaje_y_el_log(cliente):
    entorno = usar(entorno=EntornoFalso(codigo=5, log=LOG_DUPLICADO))

    respuesta = cliente.post("/respaldos/tablas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert "terminó con código 5" in cuerpo["mensaje"]
    assert "ORA-27038" in cuerpo["log"]
    assert "s3creta!" not in respuesta.text
    assert str(entorno.lecturas[0]).startswith(f"{RUTA}/ventas_")
