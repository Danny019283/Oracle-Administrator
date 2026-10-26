import os
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app

HOST = os.environ.get("ORACLE_HOST", "localhost")
PUERTO = os.environ.get("ORACLE_PORT", "1521")
CONTENEDOR = os.environ.get("ORACLE_CONTAINER", "oracle21c")
SERVICIO = "XEPDB1"

USUARIO = "TEST_RESPALDO"
DIRECTORIO = "TEST_RESPALDO_DIR"
RUTA = "/tmp/test_respaldo"


@dataclass(frozen=True)
class Entorno:
    usuario: str
    password: str
    servicio: str
    directorio: str
    ruta: str
    tabla: str


def _password_admin() -> str | None:
    if "ORACLE_DATABASE_PASSWORD" in os.environ:
        return os.environ["ORACLE_DATABASE_PASSWORD"]
    env = Path(__file__).resolve().parents[3] / ".env"
    if env.exists():
        for linea in env.read_text().splitlines():
            clave, _, valor = linea.partition("=")
            if clave.strip() == "ORACLE_DATABASE_PASSWORD":
                return valor.strip()
    return None


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", CONTENEDOR, *args], capture_output=True, text=True
    )


def _conectar_admin_tras_reinicio(password_admin: str, intentos: int = 60):
    for intento in range(intentos):
        try:
            return oracledb.connect(
                user="system", password=password_admin, dsn=f"{HOST}:{PUERTO}/{SERVICIO}"
            )
        except oracledb.Error:
            if intento == intentos - 1:
                raise
            time.sleep(3)


def _ejecutar_ignorando_errores(cursor, sql: str) -> None:
    try:
        cursor.execute(sql)
    except oracledb.DatabaseError:
        pass


@pytest.fixture(scope="session")
def entorno():
    """Usuario, tabla y DIRECTORY temporales en Oracle real; se borran al terminar."""
    password_admin = _password_admin()
    if password_admin is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para preparar la base de pruebas")
    try:
        admin = oracledb.connect(
            user="system", password=password_admin, dsn=f"{HOST}:{PUERTO}/{SERVICIO}"
        )
    except oracledb.Error as error:
        pytest.skip(f"Oracle no disponible en {HOST}:{PUERTO}/{SERVICIO}: {error}")

    password = "Tr" + secrets.token_hex(8)
    cursor = admin.cursor()
    _ejecutar_ignorando_errores(cursor, f"DROP USER {USUARIO} CASCADE")
    _ejecutar_ignorando_errores(cursor, f"DROP DIRECTORY {DIRECTORIO}")
    docker("rm", "-rf", RUTA)
    assert docker("mkdir", "-p", RUTA).returncode == 0

    cursor.execute(
        f'CREATE USER {USUARIO} IDENTIFIED BY "{password}" '
        "DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS"
    )
    cursor.execute(f"GRANT CREATE SESSION, CREATE TABLE TO {USUARIO}")
    cursor.execute(f"CREATE TABLE {USUARIO}.CLIENTES (id NUMBER, nombre VARCHAR2(50))")
    cursor.execute(f"INSERT INTO {USUARIO}.CLIENTES VALUES (1, 'Ana')")
    cursor.execute(f"INSERT INTO {USUARIO}.CLIENTES VALUES (2, 'Luis')")
    admin.commit()
    cursor.execute(f"CREATE OR REPLACE DIRECTORY {DIRECTORIO} AS '{RUTA}'")
    cursor.execute(f"GRANT READ, WRITE ON DIRECTORY {DIRECTORIO} TO {USUARIO}")

    yield Entorno(USUARIO, password, SERVICIO, DIRECTORIO, RUTA, "CLIENTES")

    # Activar ARCHIVELOG reinicia la base y corta la conexión de arriba: se abre otra.
    admin.close()
    admin = _conectar_admin_tras_reinicio(password_admin)
    cursor = admin.cursor()
    _ejecutar_ignorando_errores(cursor, f"DROP USER {USUARIO} CASCADE")
    _ejecutar_ignorando_errores(cursor, f"DROP DIRECTORY {DIRECTORIO}")
    docker("rm", "-rf", RUTA)
    admin.close()


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ORACLE_HOST", HOST)
    monkeypatch.setenv("ORACLE_PORT", PUERTO)
    monkeypatch.setenv("ORACLE_CONTAINER", CONTENEDOR)
    yield TestClient(app)
    app.dependency_overrides.clear()


def cabeceras(entorno: Entorno) -> dict[str, str]:
    respuesta = TestClient(app).post(
        "/sesion",
        json={
            "host": HOST,
            "puerto": PUERTO,
            "servicio": entorno.servicio,
            "usuario": entorno.usuario,
            "password": entorno.password,
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['token']}"}
