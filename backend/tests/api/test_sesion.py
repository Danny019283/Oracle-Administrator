import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.sesion import obtener_almacen, obtener_conector
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones

PASSWORD = "s3creta!"
CUERPO = {
    "host": "db.local",
    "puerto": 1522,
    "servicio": "XEPDB1",
    "usuario": "HR",
    "password": PASSWORD,
    "sysdba": False,
}


class ConectorFalso:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.llamadas = []

    def __call__(self, pedido):
        self.llamadas.append(pedido)
        if self.error:
            raise self.error


@pytest.fixture
def almacen():
    return AlmacenSesiones()


@pytest.fixture
def usar(almacen):
    def _usar(conector=None):
        conector = conector or ConectorFalso()
        app.dependency_overrides[obtener_almacen] = lambda: almacen
        app.dependency_overrides[obtener_conector] = lambda: conector
        return TestClient(app), conector

    yield _usar
    app.dependency_overrides.clear()


def test_login_correcto_devuelve_token_usuario_y_modo(usar, almacen):
    cliente, conector = usar()

    r = cliente.post("/sesion", json=CUERPO)

    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"token", "usuario", "sysdba"}
    assert (cuerpo["usuario"], cuerpo["sysdba"]) == ("HR", False)
    assert almacen.resolver(cuerpo["token"]) == Conexion(
        usuario="HR",
        password=PASSWORD,
        servicio="XEPDB1",
        host="db.local",
        puerto=1522,
        sysdba=False,
    )
    assert PASSWORD not in r.text
    assert len(conector.llamadas) == 1


def test_el_check_sysdba_llega_al_conector_y_a_la_sesion(usar, almacen):
    cliente, conector = usar()

    r = cliente.post("/sesion", json={**CUERPO, "sysdba": True})

    assert r.json()["sysdba"] is True
    assert conector.llamadas[0].sysdba is True
    assert almacen.resolver(r.json()["token"]).sysdba is True


def test_acepta_el_puerto_como_texto(usar):
    cliente, conector = usar()

    r = cliente.post("/sesion", json={**CUERPO, "puerto": "1521"})

    assert r.status_code == 200
    assert conector.llamadas[0].puerto == 1521


def test_datos_invalidos_responden_422_con_los_errores_y_sin_conectar(usar):
    cliente, conector = usar()

    r = cliente.post("/sesion", json={**CUERPO, "host": "", "puerto": "abc"})

    assert r.status_code == 422
    assert len(r.json()["errores"]) == 2
    assert conector.llamadas == []


def test_un_cuerpo_vacio_responde_422_con_todos_los_campos_faltantes(usar):
    cliente, conector = usar()

    r = cliente.post("/sesion", json={})

    assert r.status_code == 422
    assert len(r.json()["errores"]) == 5
    assert conector.llamadas == []


@pytest.mark.parametrize(
    "error, codigo",
    [
        ("ORA-01017: invalid username/password; logon denied", "ORA-01017"),
        ("ORA-01031: insufficient privileges", "ORA-01031"),
        ("ORA-28000: the account is locked", "ORA-28000"),
        ("ORA-28001: the password has expired", "ORA-28001"),
    ],
)
def test_credenciales_o_privilegio_invalidos_responden_401_con_mensaje_y_ora(
    usar, almacen, error, codigo
):
    cliente, _ = usar(ConectorFalso(Exception(f"{error} {PASSWORD}")))

    r = cliente.post("/sesion", json=CUERPO)

    assert r.status_code == 401
    assert r.json()["codigo"] == codigo
    assert codigo in r.json()["mensaje"]
    assert PASSWORD not in r.text


@pytest.mark.parametrize(
    "error, codigo",
    [
        ("ORA-12541: TNS:no listener", "ORA-12541"),
        ("ORA-12514: TNS:listener does not currently know of service", "ORA-12514"),
        ("DPY-6005: cannot connect to database", "DPY-6005"),
    ],
)
def test_servidor_inalcanzable_responde_502_con_mensaje_y_ora(usar, error, codigo):
    cliente, _ = usar(ConectorFalso(Exception(f"{error} {PASSWORD}")))

    r = cliente.post("/sesion", json=CUERPO)

    assert r.status_code == 502
    assert r.json()["codigo"] == codigo
    assert codigo in r.json()["mensaje"]
    assert PASSWORD not in r.text


def test_un_login_fallido_no_crea_sesion(usar, almacen):
    cliente, _ = usar(ConectorFalso(Exception("ORA-01017: invalid")))

    cliente.post("/sesion", json=CUERPO)

    assert almacen._sesiones == {}


def test_cerrar_sesion_responde_204_y_elimina_la_sesion(usar, almacen):
    cliente, _ = usar()
    token = cliente.post("/sesion", json=CUERPO).json()["token"]

    r = cliente.delete("/sesion", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 204
    assert almacen.resolver(token) is None


def test_cerrar_una_sesion_no_afecta_a_las_demas(usar, almacen):
    cliente, _ = usar()
    primero = cliente.post("/sesion", json=CUERPO).json()["token"]
    segundo = cliente.post("/sesion", json=CUERPO).json()["token"]

    cliente.delete("/sesion", headers={"Authorization": f"Bearer {primero}"})

    assert almacen.resolver(segundo) is not None


def test_cerrar_dos_veces_la_misma_sesion_responde_401_la_segunda(usar):
    cliente, _ = usar()
    token = cliente.post("/sesion", json=CUERPO).json()["token"]
    cabecera = {"Authorization": f"Bearer {token}"}

    cliente.delete("/sesion", headers=cabecera)

    assert cliente.delete("/sesion", headers=cabecera).status_code == 401


@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer desconocido"}, {"Authorization": "Basic abc"}],
)
def test_cerrar_sin_token_valido_responde_401(usar, cabeceras):
    cliente, _ = usar()

    assert cliente.delete("/sesion", headers=cabeceras).status_code == 401
