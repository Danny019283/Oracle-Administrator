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
LOG_DUPLICADO = "ORA-31641: no se puede crear el archivo\nORA-27038: el archivo creado ya existe"


def consulta_falsa(sql, params=None):
    if "user_tables" in sql.lower():
        return [("CLIENTES",)]
    return [("RESPALDO", RUTA)]


@pytest.fixture
def cliente():
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def respaldar(cliente, log):
    app.dependency_overrides[obtener_consulta] = lambda: consulta_falsa
    app.dependency_overrides[obtener_entorno] = lambda: EntornoFalso(codigo=5, log=log)
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
