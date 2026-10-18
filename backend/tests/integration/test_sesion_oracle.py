import pytest

from tests.integration.conftest import HOST, PUERTO, SERVICIO, _password_admin

pytestmark = pytest.mark.integration


def datos(entorno, **cambios):
    base = {
        "host": HOST,
        "puerto": PUERTO,
        "servicio": SERVICIO,
        "usuario": entorno.usuario,
        "password": entorno.password,
        "sysdba": False,
    }
    return {**base, **cambios}


def datos_admin(entorno, **cambios):
    admin = {"usuario": "SYS", "password": _password_admin(), "sysdba": True}
    return datos(entorno, **{**admin, **cambios})


def bearer(respuesta):
    return {"Authorization": f"Bearer {respuesta.json()['token']}"}


def test_login_con_el_usuario_de_prueba_devuelve_token_y_permite_listar_sus_tablas(cliente, entorno):
    login = cliente.post("/sesion", json=datos(entorno))

    assert login.status_code == 200
    assert login.json()["usuario"] == entorno.usuario
    assert login.json()["sysdba"] is False
    assert entorno.password not in login.text

    tablas = cliente.get("/respaldos/tablas", headers=bearer(login))
    assert tablas.status_code == 200
    assert tablas.json() == {"tablas": [entorno.tabla]}
    assert entorno.password not in tablas.text


def test_contrasena_erronea_responde_401_con_ora_01017_y_sin_sesion(cliente, entorno):
    login = cliente.post("/sesion", json=datos(entorno, password="incorrecta-123"))

    assert login.status_code == 401
    assert login.json()["codigo"] == "ORA-01017"
    assert "ORA-01017" in login.json()["mensaje"]
    assert "incorrecta-123" not in login.text
    assert "token" not in login.json()


def test_con_el_check_sysdba_y_credenciales_de_administrador_funciona(cliente, entorno):
    login = cliente.post("/sesion", json=datos_admin(entorno))

    assert login.status_code == 200
    assert login.json()["usuario"] == "SYS"
    assert login.json()["sysdba"] is True
    assert _password_admin() not in login.text


def test_la_sesion_sysdba_consulta_oracle_como_sysdba(cliente, entorno):
    login = cliente.post("/sesion", json=datos_admin(entorno))

    directorios = cliente.get("/respaldos/directorios", headers=bearer(login))

    assert directorios.status_code == 200
    assert entorno.directorio in [d["nombre"] for d in directorios.json()["directorios"]]
    assert _password_admin() not in directorios.text


def test_con_el_check_sysdba_y_sin_el_privilegio_responde_401_y_no_crea_sesion(cliente, entorno):
    login = cliente.post("/sesion", json=datos(entorno, sysdba=True))

    # En una conexión por red Oracle no distingue «sin privilegio SYSDBA» de credenciales
    # inválidas: responde ORA-01017. ORA-01031 solo aparece con autenticación local.
    assert login.status_code == 401
    assert login.json()["codigo"] == "ORA-01017"
    assert "privilegio SYSDBA" in login.json()["mensaje"]
    assert "token" not in login.json()
    assert entorno.password not in login.text


def test_sys_sin_el_check_sysdba_responde_401_con_ora_28009_y_pide_marcar_la_casilla(cliente, entorno):
    login = cliente.post("/sesion", json=datos_admin(entorno, sysdba=False))

    assert login.status_code == 401
    assert login.json()["codigo"] == "ORA-28009"
    assert "Iniciar como SYSDBA" in login.json()["mensaje"]
    assert "token" not in login.json()
    assert _password_admin() not in login.text


def test_sin_el_check_sysdba_la_contrasena_erronea_no_menciona_el_privilegio(cliente, entorno):
    login = cliente.post("/sesion", json=datos(entorno, password="incorrecta-123"))

    assert "SYSDBA" not in login.json()["mensaje"]


def test_cada_token_consulta_con_las_credenciales_de_su_propia_sesion(cliente, entorno):
    usuario = cliente.post("/sesion", json=datos(entorno))
    admin = cliente.post("/sesion", json=datos_admin(entorno))

    del_usuario = cliente.get("/respaldos/tablas", headers=bearer(usuario))
    del_admin = cliente.get("/respaldos/tablas", headers=bearer(admin))

    assert del_usuario.json() == {"tablas": [entorno.tabla]}
    assert entorno.tabla not in del_admin.json().get("tablas", [])


def test_despues_de_cerrar_la_sesion_el_token_responde_401(cliente, entorno):
    login = cliente.post("/sesion", json=datos(entorno))
    cabecera = bearer(login)
    assert cliente.get("/respaldos/tablas", headers=cabecera).status_code == 200

    cierre = cliente.delete("/sesion", headers=cabecera)

    assert cierre.status_code == 204
    assert cliente.get("/respaldos/tablas", headers=cabecera).status_code == 401
    assert cliente.delete("/sesion", headers=cabecera).status_code == 401


def test_sin_token_toda_ruta_de_respaldos_responde_401(cliente, entorno):
    assert cliente.get("/respaldos/tablas").status_code == 401
    assert cliente.get("/respaldos/directorios").status_code == 401


def test_un_host_o_puerto_inalcanzable_responde_502_y_no_crea_sesion(cliente, entorno):
    login = cliente.post("/sesion", json=datos(entorno, puerto="1999"))

    assert login.status_code == 502
    assert login.json()["codigo"] == "DPY-6005"
    assert "token" not in login.json()
    assert entorno.password not in login.text
