import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.dependencias import obtener_entorno
from src.api.respaldos import obtener_consulta
from src.api.sesion import obtener_almacen
from src.services.entorno_oracle import HerramientaNoDisponible
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones
from tests.services.entorno_falso import EntornoFalso

ALMACEN = AlmacenSesiones()
TOKEN = ALMACEN.crear(Conexion(usuario="SYS", password="s3creta!", servicio="XE", sysdba=True))
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
RUTA = "/opt/oracle/Respaldos"

CASOS = [
    ("/respaldos/tablas", {"tablas": ["CLIENTES"], "directorio": "RESPALDO", "nombre": "v"}, "expdp"),
    ("/respaldos/schemas", {"schemas": ["HR"], "directorio": "RESPALDO", "nombre": "v"}, "expdp"),
    ("/respaldos/full", {"directorio": "RESPALDO", "nombre": "v"}, "rman"),
    ("/respaldos/full/archivelog", None, "sqlplus"),
    ("/respaldos/full/archivelog", None, "docker"),
    ("/respaldos/full", {"directorio": "RESPALDO", "nombre": "v"}, "podman"),
]


class ConsultaFalsa:
    def __call__(self, sql, params=None):
        texto = sql.lower()
        if "v$database" in texto:
            return [("ARCHIVELOG",)]
        if "user_tables" in texto:
            return [("CLIENTES",)]
        if "dba_users" in texto or "all_users" in texto:
            return [("HR",)]
        return [("RESPALDO", RUTA)]


class EntornoSinHerramienta(EntornoFalso):
    def __init__(self, herramienta):
        super().__init__()
        self.herramienta = herramienta

    def crear_carpeta(self, ruta):
        raise HerramientaNoDisponible(self.herramienta)

    def ejecutar_herramienta(self, *args, **kwargs):
        raise HerramientaNoDisponible(self.herramienta)


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ORACLE_FRA_DIRECTORIO", "/opt/oracle/fra")
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    app.dependency_overrides[obtener_consulta] = lambda: ConsultaFalsa()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("ruta, cuerpo, herramienta", CASOS)
def test_si_la_herramienta_no_esta_disponible_responde_500_con_mensaje_que_la_nombra(
    cliente, ruta, cuerpo, herramienta
):
    app.dependency_overrides[obtener_entorno] = lambda: EntornoSinHerramienta(herramienta)

    respuesta = cliente.post(ruta, json=cuerpo, headers=CABECERAS)

    assert respuesta.status_code == 500
    assert herramienta in respuesta.json()["mensaje"]
    assert "Traceback" not in respuesta.text
    assert "s3creta!" not in respuesta.text
