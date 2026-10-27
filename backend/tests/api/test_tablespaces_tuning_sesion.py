import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.sesion import obtener_almacen
from src.services.expdp_runner import Conexion
from src.services.sesiones import INACTIVIDAD_MAXIMA, AlmacenSesiones
from tests.api.test_tablespaces_api import ConsultaFalsa as ConsultaTablespaces
from tests.api.test_tuning_api import ConsultaFalsa as ConsultaTuning
from tests.api.test_tuning_api import SesionFalsa

SESION = Conexion(
    usuario="SYS", password="s3creta!", servicio="XE", host="db.sesion", puerto=1555, sysdba=True
)
CABECERAS_ANTIGUAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}

# Una ruta de lectura y otra de escritura por módulo; la de Tunning abre además una sesión de varios pasos.
RUTAS = [
    ("get", "/tablespaces", None),
    ("post", "/tablespaces", {"nombre": "TS_X", "archivo": "ts_x01.dbf"}),
    ("get", "/tuning/catalogos", None),
    ("post", "/tuning/plan", {"sql": "SELECT 1 FROM dual", "schema": "HR"}),
]


class RelojFalso:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora


class Fabricas:
    """Sustituye las fábricas de conexión a Oracle y anota con qué sesión se pidieron."""

    def __init__(self):
        self.consultas: list[Conexion] = []
        self.sentencias: list[Conexion] = []
        self.sesiones: list[Conexion] = []

    def consulta(self, conexion):
        self.consultas.append(conexion)
        return lambda sql, params=None: ConsultaTuning()(sql, params) or ConsultaTablespaces()(sql, params)

    def sentencia(self, conexion):
        self.sentencias.append(conexion)
        return lambda sql, params=None: None

    def sesion(self, conexion):
        self.sesiones.append(conexion)
        return SesionFalsa()

    @property
    def todas(self):
        return self.consultas + self.sentencias + self.sesiones


@pytest.fixture
def entorno(monkeypatch):
    reloj = RelojFalso()
    almacen = AlmacenSesiones(reloj)
    fabricas = Fabricas()
    monkeypatch.setattr("src.api.admin_comun.consulta_oracle", fabricas.consulta)
    monkeypatch.setattr("src.api.admin_comun.sentencia_oracle", fabricas.sentencia)
    monkeypatch.setattr("src.api.admin_comun.sesion_oracle", fabricas.sesion)
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    yield TestClient(app), almacen, reloj, fabricas
    app.dependency_overrides.clear()


def pedir(cliente, metodo, ruta, cuerpo, cabeceras):
    envio = getattr(cliente, metodo)
    if cuerpo is None:
        return envio(ruta, headers=cabeceras)
    return envio(ruta, json=cuerpo, headers=cabeceras)


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_sin_token_responde_401_y_no_conecta_con_oracle(entorno, metodo, ruta, cuerpo):
    cliente, _, _, fabricas = entorno

    respuesta = pedir(cliente, metodo, ruta, cuerpo, {})

    assert respuesta.status_code == 401
    assert fabricas.todas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_un_token_desconocido_responde_401(entorno, metodo, ruta, cuerpo):
    cliente, _, _, fabricas = entorno

    respuesta = pedir(cliente, metodo, ruta, cuerpo, {"Authorization": "Bearer desconocido"})

    assert respuesta.status_code == 401
    assert fabricas.todas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_un_token_expirado_responde_401(entorno, metodo, ruta, cuerpo):
    cliente, almacen, reloj, fabricas = entorno
    token = almacen.crear(SESION)
    reloj.ahora += INACTIVIDAD_MAXIMA + 1

    respuesta = pedir(cliente, metodo, ruta, cuerpo, {"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert fabricas.todas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_las_cabeceras_x_oracle_ya_no_autentican(entorno, metodo, ruta, cuerpo):
    cliente, _, _, fabricas = entorno

    respuesta = pedir(cliente, metodo, ruta, cuerpo, CABECERAS_ANTIGUAS)

    assert respuesta.status_code == 401
    assert fabricas.todas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_con_token_opera_con_la_conexion_de_la_sesion(entorno, metodo, ruta, cuerpo):
    cliente, almacen, _, fabricas = entorno
    token = almacen.crear(SESION)

    respuesta = pedir(cliente, metodo, ruta, cuerpo, {"Authorization": f"Bearer {token}"})

    assert respuesta.status_code != 401
    assert fabricas.todas and all(conexion == SESION for conexion in fabricas.todas)
    assert "s3creta!" not in respuesta.text


def test_el_plan_de_ejecucion_abre_su_sesion_de_varios_pasos_con_la_conexion_del_token(entorno):
    cliente, almacen, _, fabricas = entorno
    token = almacen.crear(SESION)

    respuesta = cliente.post(
        "/tuning/plan",
        json={"sql": "SELECT 1 FROM dual", "schema": "HR"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert fabricas.sesiones == [SESION]


def test_cada_token_opera_con_las_credenciales_de_su_propia_sesion(entorno):
    cliente, almacen, _, fabricas = entorno
    otra = Conexion(usuario="HR", password="otra-clave", servicio="XEPDB1")
    token_sys, token_hr = almacen.crear(SESION), almacen.crear(otra)

    cliente.get("/tablespaces", headers={"Authorization": f"Bearer {token_sys}"})
    cliente.get("/tablespaces", headers={"Authorization": f"Bearer {token_hr}"})

    assert fabricas.consultas == [SESION, otra]
