import re
from pathlib import PurePosixPath

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin
from src.api.dependencias import obtener_conexion, obtener_entorno
from src.services.entorno_oracle import ArchivoEntorno
from src.services.expdp_runner import Conexion
from tests.services.entorno_falso import EntornoFalso

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}
DUMP = "hr_20240101_100000"
LOG_OK = "Job successfully completed"
ARCHIVOS = {
    PurePosixPath("/respaldos"): [
        ArchivoEntorno(f"{DUMP}.dmp", 100, 0),
        ArchivoEntorno(f"{DUMP}.log", 5, 0),
    ]
}


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(entorno, roles=(("DBA",),), sysdba=False):
    def consulta(sql, params=None):
        if "session_roles" in sql.lower():
            return list(roles)
        if "instance_name" in sql.lower():
            return [("XE",)]
        return [("BACKUP", "/respaldos")]

    app.dependency_overrides[obtener_consulta_admin] = lambda: consulta
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    app.dependency_overrides[obtener_conexion] = lambda: Conexion("SYSTEM", "s3creta!", "XEPDB1", sysdba=sysdba)


def recuperar(cliente, cuerpo, directorio="backup", base=DUMP):
    return cliente.post(f"/directorios/{directorio}/respaldos/{base}/recuperar", headers=CABECERAS, json=cuerpo)


CUERPO = {"modo": "datapump", "objeto_modo": "tablas", "objetos": ["hr.employees"]}


def test_recupera_con_datapump_y_responde_mensaje_log_y_sin_advertencia(cliente):
    entorno = EntornoFalso(log=LOG_OK, archivos=ARCHIVOS)
    usar(entorno)

    respuesta = recuperar(cliente, CUERPO)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "mensaje": f"Respaldo {DUMP} recuperado",
        "log": LOG_OK,
        "advertencia": None,
    }
    herramienta = entorno.herramientas[0]
    assert herramienta["nombre"] == "impdp"
    lineas = herramienta["script"].splitlines()[1:]
    assert lineas[:3] == ["DIRECTORY=BACKUP", f"DUMPFILE={DUMP}.dmp", lineas[2]]
    assert re.fullmatch(rf"LOGFILE={DUMP}_recuperacion_\d{{8}}-\d{{6}}\.log", lineas[2])
    assert lineas[3:] == ["TABLES=HR.EMPLOYEES", "TABLE_EXISTS_ACTION=SKIP"]


def test_modo_schemas_y_accion_sobre_existentes_llegan_a_impdp(cliente):
    entorno = EntornoFalso(log=LOG_OK, archivos=ARCHIVOS)
    usar(entorno)

    respuesta = recuperar(
        cliente, {"modo": "datapump", "objeto_modo": "schemas", "objetos": ["hr"], "existentes": "REPLACE"}
    )

    assert respuesta.status_code == 200
    lineas = entorno.herramientas[0]["script"].splitlines()
    assert "SCHEMAS=HR" in lineas
    assert "TABLE_EXISTS_ACTION=REPLACE" in lineas


def test_respaldo_que_no_esta_completo_responde_200_con_advertencia_del_estado(cliente):
    usar(EntornoFalso(log="ORA-39151: la tabla existe", archivos=ARCHIVOS))

    respuesta = recuperar(cliente, CUERPO)

    assert respuesta.status_code == 200
    assert respuesta.json()["advertencia"] == "El respaldo tiene estado «Con errores»"


def test_con_sesion_sysdba_pasa_sin_rol_dba(cliente):
    usar(EntornoFalso(log=LOG_OK, archivos=ARCHIVOS), roles=(), sysdba=True)

    assert recuperar(cliente, CUERPO).status_code == 200


def test_sin_sysdba_ni_dba_responde_403_sin_ejecutar_impdp(cliente):
    entorno = EntornoFalso(log=LOG_OK, archivos=ARCHIVOS)
    usar(entorno, roles=())

    respuesta = recuperar(cliente, CUERPO)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "Se requiere sesión SYSDBA o rol DBA"}
    assert entorno.herramientas == []


def test_sin_sesion_responde_401(cliente):
    respuesta = cliente.post(f"/directorios/backup/respaldos/{DUMP}/recuperar", json=CUERPO)

    assert respuesta.status_code == 401
