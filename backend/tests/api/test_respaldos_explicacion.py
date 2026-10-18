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
LOG_DUPLICADO = "ORA-31641: no se puede crear el archivo\nORA-27038: el archivo creado ya existe"


def consulta_falsa(sql, params=None):
    if "user_tables" in sql.lower():
        return [("CLIENTES",)]
    return [("RESPALDO", RUTA)]


def ejecutor_que_falla(log):
    def ejecutar(args, entrada=None):
        if "expdp" in args:
            return Salida(codigo=5, texto="salida de expdp")
        if "cat" in args and entrada is None:
            return Salida(codigo=0, texto=log)
        return Salida(codigo=0, texto="")

    return ejecutar


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def respaldar(cliente, log):
    app.dependency_overrides[obtener_consulta] = lambda: consulta_falsa
    app.dependency_overrides[obtener_ejecutor] = lambda: ejecutor_que_falla(log)
    return cliente.post("/respaldos/tablas", json=SOLICITUD, headers=CABECERAS)


def test_el_500_devuelve_mensaje_explicacion_y_log(cliente):
    respuesta = respaldar(cliente, LOG_DUPLICADO)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert "terminó con código 5" in cuerpo["mensaje"]
    assert cuerpo["explicacion"] == "Ya existe un archivo de respaldo con ese nombre en el directorio"
    assert "ORA-27038" in cuerpo["log"]
    assert "s3creta!" not in respuesta.text


def test_un_error_desconocido_devuelve_la_explicacion_generica(cliente):
    respuesta = respaldar(cliente, "ORA-99999: error raro")

    assert respuesta.status_code == 500
    assert respuesta.json()["explicacion"] == (
        "Oracle devolvió un error que no está catalogado; revisa el error y el log"
    )
