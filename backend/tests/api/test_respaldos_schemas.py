import re

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.respaldos import obtener_consulta, obtener_ejecutor
from src.services.expdp_runner import Salida

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}
RUTA = "/opt/oracle/Respaldos"
SOLICITUD = {"schemas": ["HR"], "directorio": "RESPALDO", "nombre": "ventas"}


class ConsultaFalsa:
    def __init__(self, schemas=(("HR",), ("VENTAS",)), directorios=(("RESPALDO", RUTA),)):
        self.schemas = list(schemas)
        self.directorios = list(directorios)

    def __call__(self, sql, params=None):
        return self.schemas if "all_users" in sql.lower() else self.directorios


class EjecutorFalso:
    def __init__(self, codigo_expdp=0, log="ORA-27038: el archivo creado ya existe"):
        self.codigo_expdp = codigo_expdp
        self.log = log
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "expdp" in args:
            return Salida(codigo=self.codigo_expdp, texto="salida de expdp")
        if "cat" in args and entrada is None:
            return Salida(codigo=0, texto=self.log)
        return Salida(codigo=0, texto="")


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ORACLE_CONTAINER", "oracle-test")
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(consulta=None, ejecutor=None):
    consulta = consulta or ConsultaFalsa()
    ejecutor = ejecutor or EjecutorFalso()
    app.dependency_overrides[obtener_consulta] = lambda: consulta
    app.dependency_overrides[obtener_ejecutor] = lambda: ejecutor
    return ejecutor


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
    ejecutor = usar()

    respuesta = cliente.post("/respaldos/schemas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert re.fullmatch(r"ventas_\d{8}_\d{6}\.dmp", cuerpo["dmp"])
    assert cuerpo["log"] == cuerpo["dmp"].replace(".dmp", ".log")
    assert "s3creta!" not in respuesta.text

    expdp = next(args for args, _ in ejecutor.llamadas if "expdp" in args)
    assert expdp[:3] == ["docker", "exec", "oracle-test"]
    parfile = next(entrada for _, entrada in ejecutor.llamadas if entrada is not None)
    assert "SCHEMAS=HR" in parfile.splitlines()


def test_solicitud_invalida_responde_422_con_todos_los_errores_y_no_ejecuta_expdp(cliente):
    ejecutor = usar()
    solicitud = {"schemas": [], "directorio": "OTRO", "nombre": ""}

    respuesta = cliente.post("/respaldos/schemas", json=solicitud, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        "Debes seleccionar al menos un schema",
        "El directorio OTRO no está disponible",
        "Debes ingresar un nombre de dumpfile",
    ]
    assert ejecutor.llamadas == []


def test_sin_directorios_la_solicitud_se_rechaza_con_422(cliente):
    ejecutor = usar(consulta=ConsultaFalsa(directorios=[]))

    respuesta = cliente.post("/respaldos/schemas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert "El directorio RESPALDO no está disponible" in respuesta.json()["errores"]
    assert ejecutor.llamadas == []


def test_si_expdp_falla_responde_500_con_mensaje_explicacion_y_log(cliente):
    ejecutor = usar(ejecutor=EjecutorFalso(codigo_expdp=5))

    respuesta = cliente.post("/respaldos/schemas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert "terminó con código 5" in cuerpo["mensaje"]
    assert cuerpo["explicacion"] == "Ya existe un archivo de respaldo con ese nombre en el directorio"
    assert "ORA-27038" in cuerpo["log"]
    assert "s3creta!" not in respuesta.text
    lecturas = [args for args, _ in ejecutor.llamadas if "cat" in args]
    assert lecturas and lecturas[0][-1].startswith(f"{RUTA}/ventas_")
