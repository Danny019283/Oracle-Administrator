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
LECTURAS = ["/performance/resumen", "/auditoria/estado", "/seguridad/usuarios"]


@pytest.fixture
def admin(cliente, entorno):
    if _password_admin() is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para iniciar sesión como SYSDBA")
    login = cliente.post("/sesion", json=datos_admin(entorno))
    assert login.status_code == 200, login.text
    return bearer(login)


def estado_del_usuario(cliente, cabecera, usuario):
    respuesta = cliente.get("/seguridad/usuarios", headers=cabecera)
    assert respuesta.status_code == 200, respuesta.text
    return next(u["estado"] for u in respuesta.json()["usuarios"] if u["usuario"] == usuario)


@pytest.mark.parametrize("ruta", LECTURAS)
def test_con_la_sesion_de_un_administrador_los_tres_modulos_responden(cliente, admin, ruta):
    respuesta = cliente.get(ruta, headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    assert _password_admin() not in respuesta.text


def test_performance_muestra_la_instancia_de_la_base_conectada(cliente, admin):
    respuesta = cliente.get("/performance/resumen", headers=admin)

    cuerpo = respuesta.json()
    assert cuerpo["instancia"]["estado"] == "OPEN"
    assert cuerpo["indicadores"]["sesiones_total"] >= 1


def test_seguridad_lista_el_usuario_de_prueba_con_la_sesion_de_administrador(cliente, entorno, admin):
    respuesta = cliente.get("/seguridad/usuarios", headers=admin)

    assert entorno.usuario in [u["usuario"] for u in respuesta.json()["usuarios"]]


def test_una_operacion_de_escritura_funciona_con_la_sesion_sysdba(cliente, entorno, admin):
    ruta = f"/seguridad/usuarios/{entorno.usuario}"
    try:
        bloqueo = cliente.post(f"{ruta}/bloquear", headers=admin)

        assert bloqueo.status_code == 200, bloqueo.text
        assert "LOCKED" in estado_del_usuario(cliente, admin, entorno.usuario)
    finally:
        desbloqueo = cliente.post(f"{ruta}/desbloquear", headers=admin)

    assert desbloqueo.status_code == 200, desbloqueo.text
    assert estado_del_usuario(cliente, admin, entorno.usuario) == "OPEN"


def test_cada_token_opera_con_las_credenciales_de_su_propia_sesion(cliente, entorno, admin):
    login = cliente.post("/sesion", json=datos(entorno))
    usuario = bearer(login)

    del_administrador = cliente.get("/performance/resumen", headers=admin)
    del_usuario = cliente.get("/performance/resumen", headers=usuario)

    assert del_administrador.status_code == 200
    # El usuario de prueba no tiene acceso a las vistas v$: Oracle decide con su sesión.
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
