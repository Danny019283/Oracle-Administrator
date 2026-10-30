import re
from pathlib import PurePosixPath

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin
from src.api.dependencias import obtener_conexion, obtener_entorno
from src.api.sesion import obtener_almacen
from src.services.entorno_oracle import ArchivoEntorno
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones
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
        if "log_mode" in sql.lower():
            return [("ARCHIVELOG",)]
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


RMAN = "full_20240101_100000"
LOG_RMAN = "Finished backup"
ARCHIVOS_RMAN = {
    PurePosixPath("/respaldos"): [
        ArchivoEntorno(f"{RMAN}_XE_1_1.dbf", 100, 0),
        ArchivoEntorno(f"{RMAN}.log", 5, 0),
    ]
}
FULL = {"modo": "full"}
TABLA = {"modo": "tabla", "tabla": "hr.employees", "hasta": "2024-06-01 09:00:00", "nuevo_nombre": "employees_ayer"}


@pytest.fixture
def almacen():
    almacen = AlmacenSesiones()
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    return almacen


def sesion_abierta(almacen):
    token = almacen.crear(Conexion("SYSTEM", "s3creta!", "XEPDB1", sysdba=True))
    return token


@pytest.mark.parametrize("cuerpo", [FULL, TABLA])
def test_full_y_tabla_sin_sysdba_responden_403_sin_ejecutar_rman_ni_cerrar_sesiones(cliente, almacen, cuerpo):
    entorno = EntornoFalso(log=LOG_RMAN, archivos=ARCHIVOS_RMAN)
    usar(entorno, roles=(("DBA",),), sysdba=False)
    token = sesion_abierta(almacen)

    respuesta = recuperar(cliente, cuerpo, base=RMAN)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "Se requiere sesión SYSDBA"}
    assert entorno.herramientas == []
    assert almacen.resolver(token) is not None


def test_full_con_sysdba_recupera_cierra_las_sesiones_y_lo_indica(cliente, almacen):
    entorno = EntornoFalso(log=LOG_RMAN, archivos=ARCHIVOS_RMAN)
    usar(entorno, sysdba=True)
    token = sesion_abierta(almacen)

    respuesta = recuperar(cliente, FULL, base=RMAN)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "mensaje": f"Respaldo {RMAN} recuperado",
        "log": LOG_RMAN,
        "advertencia": None,
        "sesion_cerrada": True,
    }
    assert entorno.herramientas[0]["nombre"] == "rman"
    assert entorno.herramientas[0]["script"].startswith("SHUTDOWN IMMEDIATE;\nSTARTUP MOUNT;")
    assert "SET UNTIL TIME" not in entorno.herramientas[0]["script"]
    assert entorno.herramientas[0]["args"][-1].endswith(".log")
    assert almacen.resolver(token) is None


def test_full_con_hasta_lo_lleva_al_script(cliente, almacen):
    entorno = EntornoFalso(log=LOG_RMAN, archivos=ARCHIVOS_RMAN)
    usar(entorno, sysdba=True)

    respuesta = recuperar(cliente, {**FULL, "hasta": "2024-06-01 09:00:00"}, base=RMAN)

    assert respuesta.status_code == 200
    assert "TO_DATE('01/06/2024 09:00:00','DD/MM/YYYY HH24:MI:SS')" in entorno.herramientas[0]["script"]


def test_full_que_llega_a_ejecutar_rman_y_falla_tambien_cierra_las_sesiones(almacen):
    cliente = TestClient(app, raise_server_exceptions=False)
    entorno = EntornoFalso(codigo=1, log="RMAN-03002", archivos=ARCHIVOS_RMAN)
    usar(entorno, sysdba=True)
    token = sesion_abierta(almacen)

    try:
        recuperar(cliente, FULL, base=RMAN)
    finally:
        app.dependency_overrides.clear()

    assert entorno.herramientas[0]["nombre"] == "rman"
    assert almacen.resolver(token) is None


def test_tabla_con_sysdba_recupera_sin_cerrar_las_sesiones(cliente, almacen):
    entorno = EntornoFalso(log=LOG_RMAN, archivos=ARCHIVOS_RMAN)
    usar(entorno, sysdba=True)
    token = sesion_abierta(almacen)

    respuesta = recuperar(cliente, TABLA, base=RMAN)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["mensaje"] == f"Respaldo {RMAN} recuperado"
    assert cuerpo["log"] == LOG_RMAN
    assert not cuerpo.get("sesion_cerrada")
    script = entorno.herramientas[0]["script"]
    assert script.startswith('RECOVER TABLE "HR"."EMPLOYEES"')
    assert 'REMAP TABLE "HR"."EMPLOYEES":"EMPLOYEES_AYER"' in script
    assert almacen.resolver(token) is not None
