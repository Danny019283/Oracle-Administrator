from pathlib import Path, PurePosixPath, PureWindowsPath

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
TOKEN = ALMACEN.crear(Conexion(usuario="SYS", password="s3creta!", servicio="XE", sysdba=True))
SYSDBA = {"Authorization": f"Bearer {TOKEN}"}


class EntornoFalsoLocal(EntornoFalso):
    tipo_ruta = Path


class EntornoFalsoWindows(EntornoFalso):
    tipo_ruta = PureWindowsPath


def consulta_con_carpeta(carpeta):
    def consulta(sql, params=None):
        return [(carpeta,)] if "INSTR(file_name" in sql else [("XE",)]

    return consulta


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.delenv("ORACLE_FRA_DIRECTORIO", raising=False)
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(entorno):
    # el SID sale de la consulta: se inyecta una falsa para no abrir una conexión real
    app.dependency_overrides[obtener_consulta] = lambda: lambda sql, params=None: [("XE",)]
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    return entorno


def test_en_contenedor_sin_variable_la_fra_es_la_de_hoy(cliente):
    entorno = usar(EntornoFalso())

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert entorno.carpetas == [PurePosixPath("/opt/oracle/oradata/fast_recovery_area")]


def test_la_fra_sale_de_oracle_fra_directorio(cliente, monkeypatch):
    monkeypatch.setenv("ORACLE_FRA_DIRECTORIO", "/u01/fra")
    entorno = usar(EntornoFalso())

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert entorno.carpetas == [PurePosixPath("/u01/fra")]
    assert "db_recovery_file_dest='/u01/fra'" in entorno.herramientas[0]["script"]


def test_en_local_con_variable_usa_la_ruta_del_so_de_la_estrategia(cliente, monkeypatch):
    monkeypatch.setenv("ORACLE_FRA_DIRECTORIO", "/u01/fra")
    entorno = usar(EntornoFalsoLocal())

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert entorno.carpetas == [Path("/u01/fra")]
    assert isinstance(entorno.carpetas[0], Path)


def test_en_local_sin_variable_deriva_la_ruta_de_la_consulta_y_la_usa(cliente):
    entorno = usar(EntornoFalsoWindows())
    app.dependency_overrides[obtener_consulta] = lambda: consulta_con_carpeta("C:\\APP\\ORADATA\\XE\\")

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    fra = PureWindowsPath("C:\\APP\\ORADATA\\fast_recovery_area")
    assert respuesta.status_code == 200
    assert entorno.carpetas == [fra]
    assert f"db_recovery_file_dest='{fra}'" in entorno.herramientas[0]["script"]


def test_en_local_sin_variable_y_sin_carpeta_pide_configurarla_y_no_ejecuta_nada(cliente):
    entorno = usar(EntornoFalsoLocal())
    app.dependency_overrides[obtener_consulta] = lambda: consulta_con_carpeta(None)

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert "ORACLE_FRA_DIRECTORIO" in respuesta.json()["mensaje"]
    assert entorno.carpetas == []
    assert entorno.herramientas == []
