import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.dependencias import obtener_entorno
from src.api.sesion import obtener_almacen
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones
from tests.services.entorno_falso import EntornoFalso

CONEXION = Conexion(
    usuario="SESION_USER",
    password="clave-de-sesion",
    servicio="SVC_SESION",
    host="db.sesion",
    puerto=1555,
    sysdba=False,
)
RUTA = "/opt/oracle/Respaldos"
RUTAS = [
    ("get", "/respaldos/tablas", None),
    ("get", "/respaldos/schemas", None),
    ("get", "/respaldos/directorios", None),
    (
        "post",
        "/respaldos/tablas",
        {"tablas": ["CLIENTES"], "directorio": "RESPALDO", "nombre": "ventas"},
    ),
    (
        "post",
        "/respaldos/schemas",
        {"schemas": ["HR"], "directorio": "RESPALDO", "nombre": "ventas"},
    ),
]


class RelojFalso:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora


def consulta_falsa(sql, params=None):
    sql = sql.lower()
    if "user_tables" in sql:
        return [("CLIENTES",)]
    if "all_users" in sql:
        return [("HR",)]
    return [("RESPALDO", RUTA)]


@pytest.fixture
def reloj():
    return RelojFalso()


@pytest.fixture
def almacen(reloj):
    return AlmacenSesiones(reloj=reloj)


@pytest.fixture
def cliente(almacen):
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    yield TestClient(app)
    app.dependency_overrides.clear()


def llamar(cliente, metodo, ruta, cuerpo, cabeceras):
    if metodo == "get":
        return cliente.get(ruta, headers=cabeceras)
    return cliente.post(ruta, json=cuerpo, headers=cabeceras)


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
@pytest.mark.parametrize(
    "cabeceras",
    [
        {},
        {"Authorization": "Bearer desconocido"},
        {"Authorization": "Basic abc"},
        {
            "X-Oracle-User": "HR",
            "X-Oracle-Password": "s3creta!",
            "X-Oracle-Service": "XEPDB1",
        },
    ],
    ids=["sin-token", "token-desconocido", "esquema-basic", "cabeceras-antiguas"],
)
def test_sin_token_valido_toda_ruta_de_respaldos_responde_401(
    cliente, metodo, ruta, cuerpo, cabeceras
):
    assert llamar(cliente, metodo, ruta, cuerpo, cabeceras).status_code == 401


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_una_sesion_expirada_responde_401(cliente, almacen, reloj, metodo, ruta, cuerpo):
    token = almacen.crear(CONEXION)
    reloj.ahora += 15 * 60 + 1

    respuesta = llamar(cliente, metodo, ruta, cuerpo, {"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS)
def test_una_sesion_cerrada_responde_401(cliente, almacen, metodo, ruta, cuerpo):
    token = almacen.crear(CONEXION)
    almacen.cerrar(token)

    respuesta = llamar(cliente, metodo, ruta, cuerpo, {"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


def test_las_consultas_usan_la_conexion_de_la_sesion(cliente, almacen, monkeypatch):
    recibidas = []

    def consulta_oracle(conexion):
        recibidas.append(conexion)
        return consulta_falsa

    monkeypatch.setattr("src.api.respaldos.consulta_oracle", consulta_oracle)
    token = almacen.crear(CONEXION)

    respuesta = cliente.get("/respaldos/tablas", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert recibidas == [CONEXION]


def test_el_respaldo_usa_las_credenciales_de_la_sesion(cliente, almacen, monkeypatch):
    monkeypatch.setattr("src.api.respaldos.consulta_oracle", lambda conexion: consulta_falsa)
    entorno = EntornoFalso()
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    token = almacen.crear(CONEXION)

    respuesta = cliente.post(
        "/respaldos/tablas",
        json=RUTAS[3][2],
        headers={"Authorization": f"Bearer {token}"},
    )

    assert respuesta.status_code == 200
    parfile = entorno.herramientas[0]["script"]
    assert "USERID=SESION_USER/clave-de-sesion@db.sesion:1555/SVC_SESION" in parfile.splitlines()
    assert "clave-de-sesion" not in respuesta.text


def test_cada_token_usa_su_propia_conexion(cliente, almacen, monkeypatch):
    recibidas = []

    def consulta_oracle(conexion):
        recibidas.append(conexion.usuario)
        return consulta_falsa

    monkeypatch.setattr("src.api.respaldos.consulta_oracle", consulta_oracle)
    otra = Conexion(usuario="OTRO", password="x", servicio="S")
    token_a = almacen.crear(CONEXION)
    token_b = almacen.crear(otra)

    cliente.get("/respaldos/tablas", headers={"Authorization": f"Bearer {token_a}"})
    cliente.get("/respaldos/tablas", headers={"Authorization": f"Bearer {token_b}"})

    assert recibidas == ["SESION_USER", "OTRO"]


def test_iniciar_sesion_no_exige_token(cliente):
    respuesta = cliente.post("/sesion", json={})

    assert respuesta.status_code == 422
