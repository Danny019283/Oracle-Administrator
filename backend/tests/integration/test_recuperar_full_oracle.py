import os
import re
import time
from datetime import datetime

import oracledb
import pytest

from src.services.entorno_fabrica import fabrica_desde_variables
from src.services.expdp_runner import Conexion
from src.services.instancia import sid_de_instancia
from src.services.oracle_conexion import consulta_oracle
from src.services.recuperacion import RecuperacionFallida, recuperar_full
from tests.integration.conftest import (
    CONTENEDOR,
    HOST,
    PUERTO,
    SERVICIO,
    _conectar_admin_tras_reinicio,
    _password_admin,
    docker,
)
from tests.integration.test_respaldo_full_oracle import esperar_a_que_oracle_responda, login_admin

# `skipif` se evalúa antes de montar ninguna fixture: la fixture `entorno` (de sesión) ya se conecta
# a Oracle y crea usuarios, así que un `pytest.skip` dentro del test llegaría tarde.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("ORACLE_BASE_DESECHABLE") != "1",
        reason="restore full destructivo: define ORACLE_BASE_DESECHABLE=1 solo en una base desechable",
    ),
]

PREFIJO = "recfull"
TABLA = "TEST_RECFULL"


@pytest.fixture
def admin(cliente, entorno):
    if _password_admin() is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para recuperar como SYSDBA")
    cabecera = login_admin(cliente, entorno)
    if not cliente.get("/respaldos/full/estado", headers=cabecera).json()["archivelog"]:
        assert cliente.post("/respaldos/full/archivelog", headers=cabecera).status_code == 200
        esperar_a_que_oracle_responda(_password_admin())
        cabecera = login_admin(cliente, entorno)
    return cabecera


@pytest.fixture(autouse=True)
def limpiar(entorno):
    yield
    docker("sh", "-c", f"rm -rf {entorno.ruta}/{PREFIJO}*")
    # tras el restore la base se reabrió: se abre una conexión nueva
    with _conectar_admin_tras_reinicio(_password_admin()) as bd:
        try:
            bd.cursor().execute(f"DROP TABLE {entorno.usuario}.{TABLA} PURGE")
        except oracledb.DatabaseError:
            pass


def test_recuperar_full_deja_la_base_abierta_con_los_datos_del_respaldo_y_el_log_en_el_directory(
    cliente, entorno, admin
):
    propietario = entorno.usuario
    with oracledb.connect(user="system", password=_password_admin(), dsn=f"{HOST}:{PUERTO}/{SERVICIO}") as bd:
        cursor = bd.cursor()
        cursor.execute(f"CREATE TABLE {propietario}.{TABLA} (id NUMBER, nombre VARCHAR2(50))")
        cursor.execute(f"INSERT INTO {propietario}.{TABLA} VALUES (1, 'Ana')")
        cursor.execute(f"INSERT INTO {propietario}.{TABLA} VALUES (2, 'Luis')")
        bd.commit()
    time.sleep(2)

    respaldo = cliente.post(
        "/respaldos/full", json={"directorio": entorno.directorio, "nombre": PREFIJO}, headers=admin
    )
    assert respaldo.status_code == 200, respaldo.text
    base = next(
        a.removesuffix(".log") for a in docker("ls", entorno.ruta).stdout.split() if a.startswith(f"{PREFIJO}_") and a.endswith(".log")
    )

    time.sleep(2)
    hasta = datetime.now()
    time.sleep(2)
    with oracledb.connect(user="system", password=_password_admin(), dsn=f"{HOST}:{PUERTO}/{SERVICIO}") as bd:
        cursor = bd.cursor()
        cursor.execute(f"DELETE FROM {propietario}.{TABLA} WHERE id = 1")
        cursor.execute(f"INSERT INTO {propietario}.{TABLA} VALUES (3, 'Eva')")
        bd.commit()
    time.sleep(1)

    conexion = Conexion("SYS", _password_admin(), SERVICIO, HOST, int(PUERTO), sysdba=True)
    consulta = consulta_oracle(conexion)
    entorno_oracle = fabrica_desde_variables({"ORACLE_ENTORNO": "contenedor", "ORACLE_CONTAINER": CONTENEDOR}, "linux")
    try:
        recuperar_full(
            consulta,
            entorno_oracle,
            entorno.directorio,
            base,
            hasta.strftime("%Y-%m-%d %H:%M:%S"),
            sid_de_instancia(consulta),
            datetime.now(),
        )
    except RecuperacionFallida as error:
        pytest.fail(f"El restore full falló ({error.explicacion}). Log de RMAN:\n{error.log}")

    # la sesión de `consulta` murió con el SHUTDOWN: se reconecta cuando la base reabre
    with _conectar_admin_tras_reinicio(_password_admin()) as bd:
        cursor = bd.cursor()
        cursor.execute("SELECT open_mode FROM v$database")
        assert cursor.fetchone() == ("READ WRITE",)
        cursor.execute(f"SELECT id, nombre FROM {propietario}.{TABLA} ORDER BY id")
        assert cursor.fetchall() == [(1, "Ana"), (2, "Luis")]

    logs = [a for a in docker("ls", entorno.ruta).stdout.split() if re.fullmatch(rf"{re.escape(base)}_recuperacion_\d{{8}}-\d{{6}}\.log", a)]
    assert len(logs) == 1
