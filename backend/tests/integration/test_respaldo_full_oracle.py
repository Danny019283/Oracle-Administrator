import time

import oracledb
import pytest

from tests.integration.conftest import HOST, PUERTO, SERVICIO, _password_admin, docker
from tests.integration.test_sesion_oracle import bearer, datos_admin

pytestmark = pytest.mark.integration

ESPERA_REINICIO = 240


def esperar_a_que_oracle_responda(password: str) -> None:
    """Tras activar ARCHIVELOG la base se reinicia: espera a que acepte conexiones."""
    limite = time.monotonic() + ESPERA_REINICIO
    while True:
        try:
            oracledb.connect(
                user="sys",
                password=password,
                dsn=f"{HOST}:{PUERTO}/{SERVICIO}",
                mode=oracledb.AUTH_MODE_SYSDBA,
            ).close()
            return
        except oracledb.Error:
            if time.monotonic() > limite:
                raise
            time.sleep(3)


def login_admin(cliente, entorno):
    login = cliente.post("/sesion", json=datos_admin(entorno))
    assert login.status_code == 200, login.text
    return bearer(login)


@pytest.fixture
def admin(cliente, entorno):
    if _password_admin() is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para iniciar sesión como SYSDBA")
    return login_admin(cliente, entorno)


def test_una_sesion_sin_sysdba_no_puede_usar_las_rutas_de_full(cliente, entorno):
    from tests.integration.test_sesion_oracle import datos

    login = cliente.post("/sesion", json=datos(entorno))
    cabecera = bearer(login)

    assert cliente.get("/respaldos/full/estado", headers=cabecera).status_code == 403
    assert cliente.post("/respaldos/full/archivelog", headers=cabecera).status_code == 403
    assert (
        cliente.post(
            "/respaldos/full",
            json={"directorio": entorno.directorio, "nombre": "no_debe_ejecutarse"},
            headers=cabecera,
        ).status_code
        == 403
    )


def test_activa_archivelog_y_la_base_queda_en_ese_modo(cliente, entorno, admin):
    if cliente.get("/respaldos/full/estado", headers=admin).json()["archivelog"]:
        return  # Ya estaba activado en una ejecución anterior.

    respuesta = cliente.post("/respaldos/full/archivelog", headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["mensaje"] == "ARCHIVELOG activado. Inicia sesión de nuevo"
    assert _password_admin() not in respuesta.text

    esperar_a_que_oracle_responda(_password_admin())
    nueva = login_admin(cliente, entorno)
    assert cliente.get("/respaldos/full/estado", headers=nueva).json() == {"archivelog": True}


def test_el_respaldo_full_deja_las_piezas_en_el_directorio_sin_residuos(cliente, entorno, admin):
    solicitud = {"directorio": entorno.directorio, "nombre": "full_integracion"}

    respuesta = cliente.post("/respaldos/full", json=solicitud, headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert "Finished backup" in cuerpo["log"] or "backup set complete" in cuerpo["log"]
    assert cuerpo["advertencia"] is None, cuerpo["advertencia"]
    assert _password_admin() not in respuesta.text

    piezas = docker("ls", entorno.ruta)
    assert piezas.returncode == 0, piezas.stderr
    assert [p for p in piezas.stdout.split() if p.startswith("full_integracion_")]

    residuos = docker("sh", "-c", "ls /tmp/rman_* /tmp/archivelog_* 2>/dev/null")
    assert residuos.stdout.strip() == ""


def test_un_nombre_invalido_no_ejecuta_rman(cliente, entorno, admin):
    solicitud = {"directorio": entorno.directorio, "nombre": "con espacios"}

    respuesta = cliente.post("/respaldos/full", json=solicitud, headers=admin)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"]
