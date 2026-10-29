import json
from pathlib import PureWindowsPath

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin, responder
from src.api.dependencias import obtener_entorno
from src.services.directorios import DirectorioInvalido, DirectorioNoEncontrado
from src.services.entorno_oracle import OperacionEntornoFallida
from tests.services.entorno_falso import EntornoFalso

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}


class EntornoWindows(EntornoFalso):
    tipo_ruta = PureWindowsPath


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(filas, entorno=None):
    app.dependency_overrides[obtener_consulta_admin] = lambda: lambda sql, params=None: filas
    app.dependency_overrides[obtener_entorno] = lambda: entorno or EntornoFalso()


def test_lista_los_directorios_con_nombre_y_ruta_y_los_ejemplos(cliente):
    usar([("BACKUP", "/opt/oracle/respaldos"), ("DATA_PUMP_DIR", "/u01/dpdump")])

    respuesta = cliente.get("/directorios", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "directorios": [
            {"nombre": "BACKUP", "ruta": "/opt/oracle/respaldos"},
            {"nombre": "DATA_PUMP_DIR", "ruta": "/u01/dpdump"},
        ],
        "ejemplos_ruta": ["/opt/oracle/respaldos"],
    }


def test_los_ejemplos_dependen_del_entorno(cliente):
    usar([], EntornoWindows())

    respuesta = cliente.get("/directorios", headers=CABECERAS)

    assert respuesta.json()["ejemplos_ruta"] == ["C:\\respaldos", "\\\\servidor\\recurso"]


def test_sin_directorios_responde_200_con_lista_vacia(cliente):
    usar([])

    respuesta = cliente.get("/directorios", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json()["directorios"] == []


def test_sin_sesion_responde_401(cliente):
    respuesta = cliente.get("/directorios")

    assert respuesta.status_code == 401


def _lanzar(error):
    def accion():
        raise error

    return responder(accion)


def test_responder_mapea_directorio_invalido_a_422():
    respuesta = _lanzar(DirectorioInvalido(["La ruta es obligatoria"]))

    assert respuesta.status_code == 422
    assert json.loads(respuesta.body) == {"errores": ["La ruta es obligatoria"]}


def test_responder_mapea_directorio_no_encontrado_a_404():
    respuesta = _lanzar(DirectorioNoEncontrado("El directorio X no existe"))

    assert respuesta.status_code == 404
    assert json.loads(respuesta.body) == {"detail": "El directorio X no existe"}


def test_responder_mapea_fallo_de_permisos_a_500_con_mensaje_explicacion_y_error():
    respuesta = _lanzar(OperacionEntornoFallida("chown: no such file\nmas detalle"))

    cuerpo = json.loads(respuesta.body)
    assert respuesta.status_code == 500
    assert cuerpo["mensaje"] == "No se pudieron dar permisos a Oracle sobre la carpeta"
    assert "debe existir en el contenedor" in cuerpo["explicacion"]
    assert cuerpo["error"] == "chown: no such file"
