import pytest

from tests.integration.conftest import _password_admin
from tests.integration.test_sesion_oracle import bearer, datos, datos_admin

pytestmark = pytest.mark.integration

CABECERAS_ANTIGUAS = {
    "X-Oracle-User": "SYS",
    "X-Oracle-Password": "cualquiera",
    "X-Oracle-Service": "XEPDB1",
}

# Una ruta de lectura por módulo.
LECTURAS = ["/tablespaces", "/tuning/catalogos"]


@pytest.fixture
def admin(cliente, entorno):
    if _password_admin() is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para iniciar sesión como SYSDBA")
    login = cliente.post("/sesion", json=datos_admin(entorno))
    assert login.status_code == 200, login.text
    return bearer(login)


@pytest.mark.parametrize("ruta", LECTURAS)
def test_con_la_sesion_de_un_administrador_los_dos_modulos_responden(cliente, admin, ruta):
    respuesta = cliente.get(ruta, headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    assert _password_admin() not in respuesta.text


def test_tablespaces_lista_los_de_la_base_conectada(cliente, admin):
    respuesta = cliente.get("/tablespaces", headers=admin)

    nombres = {t["nombre"] for t in respuesta.json()["tablespaces"]}
    assert {"SYSTEM", "SYSAUX", "USERS", "TEMP"} <= nombres


def test_tunning_ofrece_el_schema_de_prueba(cliente, entorno, admin):
    respuesta = cliente.get("/tuning/catalogos", headers=admin)

    assert entorno.usuario in respuesta.json()["schemas"]


def test_el_plan_de_ejecucion_funciona_con_la_sesion_sysdba(cliente, entorno, admin):
    solicitud = {
        "sql": f"SELECT * FROM {entorno.tabla} WHERE id = 1",
        "schema": entorno.usuario,
    }

    respuesta = cliente.post("/tuning/plan", json=solicitud, headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["operaciones"]
    assert _password_admin() not in respuesta.text


def test_cada_token_opera_con_las_credenciales_de_su_propia_sesion(cliente, entorno, admin):
    usuario = cliente.post("/sesion", json=datos(entorno))

    del_administrador = cliente.get("/tablespaces", headers=admin)
    del_usuario = cliente.get("/tablespaces", headers=bearer(usuario))

    assert del_administrador.status_code == 200
    # El usuario de prueba no puede consultar dba_*: Oracle decide con su sesión.
    assert del_usuario.status_code == 500
    assert del_usuario.json()["error"].startswith("ORA-")
    assert entorno.password not in del_usuario.text


@pytest.mark.parametrize("ruta", LECTURAS)
def test_sin_token_responde_401(cliente, entorno, ruta):
    assert cliente.get(ruta).status_code == 401


@pytest.mark.parametrize("ruta", LECTURAS)
def test_las_cabeceras_x_oracle_sin_token_responden_401(cliente, entorno, ruta):
    respuesta = cliente.get(ruta, headers=CABECERAS_ANTIGUAS)

    assert respuesta.status_code == 401
    assert "cualquiera" not in respuesta.text


@pytest.mark.parametrize("ruta", LECTURAS)
def test_despues_de_cerrar_la_sesion_el_token_responde_401(cliente, admin, ruta):
    assert cliente.get(ruta, headers=admin).status_code == 200

    assert cliente.delete("/sesion", headers=admin).status_code == 204

    assert cliente.get(ruta, headers=admin).status_code == 401
