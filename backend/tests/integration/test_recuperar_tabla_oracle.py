import time
from datetime import datetime

import oracledb
import pytest

from src.services.entorno_fabrica import fabrica_desde_variables
from src.services.expdp_runner import Conexion
from src.services.instancia import sid_de_instancia
from src.services.oracle_conexion import consulta_oracle
from src.services.recuperacion import RecuperacionFallida, recuperar_tabla
from tests.integration.conftest import CONTENEDOR, HOST, PUERTO, SERVICIO, _password_admin, docker
from tests.integration.test_respaldo_full_oracle import esperar_a_que_oracle_responda, login_admin

pytestmark = pytest.mark.integration

PREFIJO = "rectab"
ORIGINAL = "TEST_RECTAB"
RECUPERADA = "TEST_RECTAB_REC"


@pytest.fixture
def system():
    with oracledb.connect(user="system", password=_password_admin(), dsn=f"{HOST}:{PUERTO}/{SERVICIO}") as bd:
        yield bd.cursor()


@pytest.fixture
def admin(cliente, entorno, system):
    if _password_admin() is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para recuperar como SYSDBA")
    system.execute("SELECT banner FROM v$version")
    if any("Express Edition" in banner for (banner,) in system.fetchall()):
        pytest.skip(
            "RECOVER TABLE no puede arrancar la instancia auxiliar en Oracle Express Edition "
            "(RMAN-04014 / ORA-00442); solo se ejecuta en Enterprise o Standard"
        )
    cabecera = login_admin(cliente, entorno)
    if not cliente.get("/respaldos/full/estado", headers=cabecera).json()["archivelog"]:
        assert cliente.post("/respaldos/full/archivelog", headers=cabecera).status_code == 200
        esperar_a_que_oracle_responda(_password_admin())
        cabecera = login_admin(cliente, entorno)
    return cabecera


@pytest.fixture(autouse=True)
def limpiar(entorno, system):
    yield
    docker("sh", "-c", f"rm -rf {entorno.ruta}/{PREFIJO}* {entorno.ruta}/aux_{PREFIJO}*")
    for tabla in (ORIGINAL, RECUPERADA):
        try:
            system.execute(f"DROP TABLE {entorno.usuario}.{tabla} PURGE")
        except oracledb.DatabaseError:
            pass


def test_recupera_una_tabla_con_otro_nombre_sin_tocar_la_original_y_borra_la_carpeta_auxiliar(
    cliente, entorno, admin, system
):
    propietario = entorno.usuario
    system.execute(f"CREATE TABLE {propietario}.{ORIGINAL} (id NUMBER, nombre VARCHAR2(50))")
    system.execute(f"INSERT INTO {propietario}.{ORIGINAL} VALUES (1, 'Ana')")
    system.execute(f"INSERT INTO {propietario}.{ORIGINAL} VALUES (2, 'Luis')")
    system.execute("COMMIT")
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
    system.execute(f"INSERT INTO {propietario}.{ORIGINAL} VALUES (3, 'Eva')")
    system.execute("COMMIT")
    time.sleep(1)

    conexion = Conexion("SYS", _password_admin(), SERVICIO, HOST, int(PUERTO), sysdba=True)
    consulta = consulta_oracle(conexion)
    entorno_oracle = fabrica_desde_variables({"ORACLE_ENTORNO": "contenedor", "ORACLE_CONTAINER": CONTENEDOR}, "linux")
    try:
        recuperar_tabla(
            consulta,
            entorno_oracle,
            entorno.directorio,
            base,
            f"{propietario}.{ORIGINAL}",
            hasta.strftime("%Y-%m-%d %H:%M:%S"),
            RECUPERADA,
            sid_de_instancia(consulta),
            datetime.now(),
        )
    except RecuperacionFallida as error:
        pytest.fail(f"RECOVER TABLE falló ({error.explicacion}). Log de RMAN:\n{error.log}")

    system.execute(f"SELECT id, nombre FROM {propietario}.{RECUPERADA} ORDER BY id")
    assert system.fetchall() == [(1, "Ana"), (2, "Luis")]
    system.execute(f"SELECT id, nombre FROM {propietario}.{ORIGINAL} ORDER BY id")
    assert system.fetchall() == [(1, "Ana"), (2, "Luis"), (3, "Eva")]
    assert f"aux_{base}" not in docker("ls", entorno.ruta).stdout.split()
