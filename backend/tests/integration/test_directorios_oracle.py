import subprocess

import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app

from tests.integration.conftest import (
    HOST,
    CONTENEDOR,
    PUERTO,
    SERVICIO,
    _ejecutar_ignorando_errores,
    _password_admin,
    docker,
)

DIRECTORIO = "TEST_DIRS_OA"
CARPETA = "/tmp/test_dirs_oa"
CARPETA_NUEVA = "/tmp/test_dirs_oa_nueva"
CARPETA_INEXISTENTE = "/tmp/test_dirs_oa_no_existe"
INEXISTENTE = "TEST_DIRS_OA_NOEXISTE"
DIRECTORIO_SCHEMA = "TEST_DIRS_OA_SCH"
SCHEMA = "TEST_DIRS_OA_USR"
SCHEMA_INEXISTENTE = "TEST_DIRS_OA_NOUSR"
DIRECTORIO_SIN_SCHEMA = "TEST_DIRS_OA_NOSCH"


@pytest.fixture(scope="module")
def admin():
    """Cabecera de la sesión de SYSTEM y carpetas de prueba en el contenedor; todo se borra al terminar."""
    password = _password_admin()
    if password is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para preparar la base de pruebas")
    try:
        bd = oracledb.connect(user="system", password=password, dsn=f"{HOST}:{PUERTO}/{SERVICIO}")
    except oracledb.Error as error:
        pytest.skip(f"Oracle no disponible en {HOST}:{PUERTO}/{SERVICIO}: {error}")

    cursor = bd.cursor()

    def limpiar():
        for nombre in (DIRECTORIO, INEXISTENTE, DIRECTORIO_SCHEMA, DIRECTORIO_SIN_SCHEMA):
            _ejecutar_ignorando_errores(cursor, f"DROP DIRECTORY {nombre}")
        _ejecutar_ignorando_errores(cursor, f"DROP USER {SCHEMA} CASCADE")
        docker("rm", "-rf", CARPETA, CARPETA_NUEVA, CARPETA_INEXISTENTE)

    limpiar()
    assert docker("mkdir", "-p", CARPETA, CARPETA_NUEVA).returncode == 0
    # Carpetas de root: así se comprueba que la app las pasa a oracle.
    chown = subprocess.run(
        ["docker", "exec", "-u", "root", CONTENEDOR, "chown", "root:root", CARPETA, CARPETA_NUEVA],
        capture_output=True,
        text=True,
    )
    assert chown.returncode == 0, chown.stderr
    cursor.execute(f"CREATE USER {SCHEMA} NO AUTHENTICATION")

    login = TestClient(app).post(
        "/sesion",
        json={"host": HOST, "puerto": PUERTO, "servicio": SERVICIO, "usuario": "SYSTEM", "password": password},
    )
    assert login.status_code == 200, login.text

    yield {"cabeceras": {"Authorization": f"Bearer {login.json()['token']}"}, "cursor": cursor}

    limpiar()
    bd.close()


def _ruta(cursor, nombre):
    cursor.execute("SELECT directory_path FROM all_directories WHERE directory_name = :n", n=nombre)
    fila = cursor.fetchone()
    return fila[0] if fila else None


def _nombres(cliente, url, cabeceras):
    respuesta = cliente.get(url, headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text
    return {d["nombre"] for d in respuesta.json()["directorios"]}


@pytest.mark.integration
def test_crea_edita_y_elimina_un_directorio(cliente, admin):
    h, cursor = admin["cabeceras"], admin["cursor"]

    creado = cliente.post("/directorios", json={"nombre": DIRECTORIO.lower(), "ruta": CARPETA}, headers=h)
    assert creado.status_code == 200, creado.text
    assert creado.json()["mensaje"] == f"Directorio {DIRECTORIO} creado"
    assert _ruta(cursor, DIRECTORIO) == CARPETA
    assert DIRECTORIO in _nombres(cliente, "/directorios", h)
    assert DIRECTORIO in _nombres(cliente, "/respaldos/directorios", h)
    assert docker("stat", "-c", "%U", CARPETA).stdout.strip() == "oracle"

    repetido = cliente.post("/directorios", json={"nombre": DIRECTORIO, "ruta": CARPETA}, headers=h)
    assert repetido.status_code == 422
    assert _ruta(cursor, DIRECTORIO) == CARPETA

    editado = cliente.put(f"/directorios/{DIRECTORIO}", json={"ruta": CARPETA_NUEVA}, headers=h)
    assert editado.status_code == 200, editado.text
    assert _ruta(cursor, DIRECTORIO) == CARPETA_NUEVA
    assert docker("stat", "-c", "%U", CARPETA_NUEVA).stdout.strip() == "oracle"

    eliminado = cliente.delete(f"/directorios/{DIRECTORIO}", headers=h)
    assert eliminado.status_code == 200, eliminado.text
    assert _ruta(cursor, DIRECTORIO) is None
    assert DIRECTORIO not in _nombres(cliente, "/directorios", h)


def _privilegios(cursor, directorio, usuario):
    cursor.execute(
        "SELECT privilege FROM dba_tab_privs WHERE table_name = :d AND grantee = :u", d=directorio, u=usuario
    )
    return {fila[0] for fila in cursor.fetchall()}


@pytest.mark.integration
def test_crear_con_schema_le_da_read_y_write(cliente, admin):
    h, cursor = admin["cabeceras"], admin["cursor"]

    creado = cliente.post(
        "/directorios", json={"nombre": DIRECTORIO_SCHEMA, "ruta": CARPETA, "schema": SCHEMA.lower()}, headers=h
    )

    assert creado.status_code == 200, creado.text
    assert _ruta(cursor, DIRECTORIO_SCHEMA) == CARPETA
    assert _privilegios(cursor, DIRECTORIO_SCHEMA, SCHEMA) == {"READ", "WRITE"}
    cursor.execute(
        "SELECT privilege FROM all_tab_privs WHERE table_name = :d AND grantee = :u", d=DIRECTORIO_SCHEMA, u=SCHEMA
    )
    assert {fila[0] for fila in cursor.fetchall()} == {"READ", "WRITE"}


@pytest.mark.integration
def test_crear_con_un_schema_inexistente_da_422_y_no_crea_el_directorio(cliente, admin):
    h, cursor = admin["cabeceras"], admin["cursor"]

    respuesta = cliente.post(
        "/directorios",
        json={"nombre": DIRECTORIO_SIN_SCHEMA, "ruta": CARPETA, "schema": SCHEMA_INEXISTENTE},
        headers=h,
    )

    assert respuesta.status_code == 422, respuesta.text
    assert _ruta(cursor, DIRECTORIO_SIN_SCHEMA) is None


@pytest.mark.integration
def test_el_directorio_del_sistema_no_se_edita_ni_se_elimina(cliente, admin):
    h, cursor = admin["cabeceras"], admin["cursor"]
    antes = _ruta(cursor, "DATA_PUMP_DIR")
    assert antes is not None

    editado = cliente.put("/directorios/DATA_PUMP_DIR", json={"ruta": CARPETA}, headers=h)
    eliminado = cliente.delete("/directorios/DATA_PUMP_DIR", headers=h)

    assert editado.status_code == 422
    assert eliminado.status_code == 422
    assert _ruta(cursor, "DATA_PUMP_DIR") == antes


@pytest.mark.integration
def test_crear_con_una_carpeta_inexistente_da_500_y_no_crea_el_directorio(cliente, admin):
    h, cursor = admin["cabeceras"], admin["cursor"]
    assert docker("test", "-e", CARPETA_INEXISTENTE).returncode != 0

    respuesta = cliente.post("/directorios", json={"nombre": INEXISTENTE, "ruta": CARPETA_INEXISTENTE}, headers=h)

    assert respuesta.status_code == 500, respuesta.text
    assert {"mensaje", "explicacion", "error"} <= set(respuesta.json())
    assert _ruta(cursor, INEXISTENTE) is None
