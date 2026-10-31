import contextlib
import re
from dataclasses import replace
from datetime import datetime

import oracledb
import pytest

from src.services.archivos_respaldo import listar_respaldos
from src.services.entorno_fabrica import fabrica_desde_variables
from src.services.expdp_runner import Conexion
from src.services.oracle_conexion import consulta_oracle
from src.services.recuperacion import RecuperacionFallida, recuperar_datapump
from tests.integration.conftest import CONTENEDOR, HOST, PUERTO, SERVICIO, _password_admin, cabeceras, docker

pytestmark = pytest.mark.integration

SCHEMA = "TEST_RECDP_SCH"
PREFIJO = "recdp_"
CLAVE = "Tr0nco_sch1"


@pytest.fixture
def admin_sys():
    password = _password_admin()
    if password is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para recuperar como SYSDBA")
    conexion = Conexion("SYS", password, SERVICIO, HOST, int(PUERTO), sysdba=True)
    entorno = fabrica_desde_variables({"ORACLE_ENTORNO": "contenedor", "ORACLE_CONTAINER": CONTENEDOR}, "linux")
    return conexion, entorno, consulta_oracle(conexion)


@pytest.fixture
def system():
    with oracledb.connect(user="system", password=_password_admin(), dsn=f"{HOST}:{PUERTO}/{SERVICIO}") as bd:
        yield bd.cursor()


@pytest.fixture(autouse=True)
def limpiar(entorno):
    yield
    docker("sh", "-c", f"rm -f {entorno.ruta}/{PREFIJO}*")


def _recuperar(admin_sys, entorno, base, modo, objetos, existentes="SKIP"):
    conexion, ent, consulta = admin_sys
    return recuperar_datapump(
        consulta, ent, conexion, entorno.directorio, base, modo, objetos, existentes, datetime.now()
    )


def _entrada(admin_sys, entorno, base):
    _, ent, consulta = admin_sys
    respaldos, _ = listar_respaldos(consulta, ent)
    return [r for r in respaldos if r.directorio == entorno.directorio and r.base == base]


def _logs_de_recuperacion(entorno, base):
    salida = docker("ls", entorno.ruta)
    return [a for a in salida.stdout.split() if re.fullmatch(rf"{base}_recuperacion_\d{{8}}-\d{{6}}\.log", a)]


def _respaldar_tabla(cliente, entorno, nombre):
    respuesta = cliente.post(
        "/respaldos/tablas",
        json={"tablas": [entorno.tabla], "directorio": entorno.directorio, "nombre": nombre},
        headers=cabeceras(entorno),
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["dmp"].removesuffix(".dmp")


def test_recupera_una_tabla_borrada_con_sus_filas_y_deja_el_log(cliente, entorno, admin_sys, system):
    base = _respaldar_tabla(cliente, entorno, f"{PREFIJO}tabla")
    antes = _entrada(admin_sys, entorno, base)
    assert len(antes) == 1

    system.execute(f"DROP TABLE {entorno.usuario}.{entorno.tabla} PURGE")
    resultado = _recuperar(admin_sys, entorno, base, "tablas", [f"{entorno.usuario}.{entorno.tabla}"])

    system.execute(f"SELECT id, nombre FROM {entorno.usuario}.{entorno.tabla} ORDER BY id")
    assert system.fetchall() == [(1, "Ana"), (2, "Luis")]
    assert "successfully completed" in resultado.log
    assert len(_logs_de_recuperacion(entorno, base)) == 1
    assert _entrada(admin_sys, entorno, base) == antes


def test_recupera_un_schema_borrado_con_sus_tablas_y_filas(cliente, entorno, admin_sys, system):
    system.execute("SELECT COUNT(*) FROM dba_users WHERE username = :u", u=SCHEMA)
    if system.fetchone()[0]:
        system.execute(f"DROP USER {SCHEMA} CASCADE")
    try:
        system.execute(f'CREATE USER {SCHEMA} IDENTIFIED BY "{CLAVE}" DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS')
        system.execute(f"CREATE TABLE {SCHEMA}.PRODUCTOS (id NUMBER, nombre VARCHAR2(50))")
        system.execute(f"INSERT INTO {SCHEMA}.PRODUCTOS VALUES (7, 'Pan')")
        system.execute("COMMIT")
        # lo exporta system (rol DBA): así el dump lleva el CREATE USER y impdp puede recrear el schema
        respuesta = cliente.post(
            "/respaldos/schemas",
            json={"schemas": [SCHEMA], "directorio": entorno.directorio, "nombre": f"{PREFIJO}schema"},
            headers=cabeceras(replace(entorno, usuario='system', password=_password_admin())),
        )
        assert respuesta.status_code == 200, respuesta.text
        base = respuesta.json()["dmp"].removesuffix(".dmp")
        antes = _entrada(admin_sys, entorno, base)
        assert len(antes) == 1

        system.execute(f"DROP USER {SCHEMA} CASCADE")
        resultado = _recuperar(admin_sys, entorno, base, "schemas", [SCHEMA])

        system.execute(f"SELECT id, nombre FROM {SCHEMA}.PRODUCTOS")
        assert system.fetchall() == [(7, "Pan")]
        assert "successfully completed" in resultado.log
        assert len(_logs_de_recuperacion(entorno, base)) == 1
        assert _entrada(admin_sys, entorno, base) == antes
    finally:
        with contextlib.suppress(oracledb.DatabaseError):  # puede no existir si la recuperación falló
            system.execute(f"DROP USER {SCHEMA} CASCADE")


def test_una_recuperacion_con_nombres_inexistentes_falla_y_conserva_el_log(cliente, entorno, admin_sys):
    base = _respaldar_tabla(cliente, entorno, f"{PREFIJO}inexistente")

    with pytest.raises(RecuperacionFallida) as error:
        _recuperar(admin_sys, entorno, base, "tablas", [f"{entorno.usuario}.TEST_NO_EXISTE"])

    assert "ORA-" in error.value.log
    assert _password_admin() not in error.value.log
    assert len(_logs_de_recuperacion(entorno, base)) == 1
