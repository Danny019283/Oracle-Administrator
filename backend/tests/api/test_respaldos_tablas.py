import re

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.respaldos import obtener_consulta, obtener_ejecutor
from src.services.expdp_runner import Salida

CABECERAS = {
    "X-Oracle-User": "HR",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}
RUTA = "/opt/oracle/Respaldos"
SOLICITUD = {"tablas": ["CLIENTES"], "directorio": "RESPALDO", "nombre": "ventas"}


class ConsultaFalsa:
    def __init__(self, tablas=(("CLIENTES",), ("PEDIDOS",)), directorios=(("RESPALDO", RUTA),)):
        self.tablas = list(tablas)
        self.directorios = list(directorios)

    def __call__(self, sql, params=None):
        return self.tablas if "user_tables" in sql.lower() else self.directorios


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
    ejecutor = usar()

    respuesta = cliente.post("/respaldos/tablas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert re.fullmatch(r"ventas_\d{8}_\d{6}\.dmp", cuerpo["dmp"])
    assert cuerpo["log"] == cuerpo["dmp"].replace(".dmp", ".log")
    assert "s3creta!" not in respuesta.text

    expdp = next(args for args, _ in ejecutor.llamadas if "expdp" in args)
    assert expdp[:3] == ["docker", "exec", "oracle-test"]
    parfile = next(entrada for _, entrada in ejecutor.llamadas if entrada is not None)
    assert "USERID=HR/s3creta!@XEPDB1" in parfile.splitlines()
    assert "TABLES=CLIENTES" in parfile.splitlines()


def test_solicitud_invalida_responde_422_con_todos_los_errores_y_no_ejecuta_expdp(cliente):
    ejecutor = usar()
    solicitud = {"tablas": [], "directorio": "OTRO", "nombre": ""}

    respuesta = cliente.post("/respaldos/tablas", json=solicitud, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        "Debes seleccionar al menos una tabla",
        "El directorio OTRO no está disponible",
        "Debes ingresar un nombre de dumpfile",
    ]
    assert ejecutor.llamadas == []


def test_si_expdp_falla_responde_500_con_el_mensaje_y_el_log(cliente):
    ejecutor = usar(ejecutor=EjecutorFalso(codigo_expdp=5))

    respuesta = cliente.post("/respaldos/tablas", json=SOLICITUD, headers=CABECERAS)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert "terminó con código 5" in cuerpo["mensaje"]
    assert "ORA-27038" in cuerpo["log"]
    assert "s3creta!" not in respuesta.text
    lecturas = [args for args, _ in ejecutor.llamadas if "cat" in args]
    assert lecturas and lecturas[0][-1].startswith(f"{RUTA}/ventas_")
