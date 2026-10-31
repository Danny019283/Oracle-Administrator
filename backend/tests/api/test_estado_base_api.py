import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.dependencias import obtener_entorno
from src.services.entorno_oracle import HerramientaNoDisponible, Salida
from tests.services.entorno_falso import EntornoFalso


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(entorno):
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    return entorno


def en_estado(status, accion=Salida(0, "ok")):
    consulta = Salida(0, status) if status else Salida(1, "ORA-01034: ORACLE not available")
    return usar(EntornoFalso(salidas=[consulta, accion]))


@pytest.mark.parametrize(
    "status,estado",
    [("STARTED", "NOMOUNT"), ("MOUNTED", "MOUNT"), ("OPEN", "ABIERTA"), (None, "APAGADA")],
)
def test_get_devuelve_el_estado_sin_exigir_sesion(cliente, status, estado):
    en_estado(status)

    respuesta = cliente.get("/base/estado")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": estado}


def test_post_ejecuta_la_accion_sin_sesion_y_devuelve_mensaje_y_log(cliente):
    entorno = en_estado("MOUNTED", Salida(0, "Database altered."))

    respuesta = cliente.post("/base/estado", json={"accion": "ENCENDER"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["log"] == "Database altered."
    assert "ENCENDER" in cuerpo["mensaje"]
    assert "ALTER DATABASE OPEN;" in entorno.herramientas[1]["script"]


def test_accion_desconocida_responde_422_sin_ejecutar_nada(cliente):
    entorno = en_estado("OPEN")

    respuesta = cliente.post("/base/estado", json={"accion": "REINICIAR"})

    assert respuesta.status_code == 422
    assert entorno.herramientas == []


def test_accion_no_valida_para_el_estado_responde_409_con_mensaje(cliente):
    entorno = en_estado("OPEN")

    respuesta = cliente.post("/base/estado", json={"accion": "NOMOUNT"})

    assert respuesta.status_code == 409
    assert "NOMOUNT" in respuesta.json()["detail"] and "ABIERTA" in respuesta.json()["detail"]
    assert len(entorno.herramientas) == 1


def test_fallo_de_sqlplus_en_la_accion_responde_500_con_explicacion_y_log(cliente):
    en_estado("OPEN", Salida(1, "ORA-01031: insufficient privileges"))

    respuesta = cliente.post("/base/estado", json={"accion": "APAGAR"})

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["mensaje"] == "No se pudo cambiar el estado de la base"
    assert "privilegio" in cuerpo["explicacion"]
    assert cuerpo["log"] == "ORA-01031: insufficient privileges"


def test_fallo_de_sqlplus_en_la_consulta_responde_500_con_log(cliente):
    usar(EntornoFalso(codigo=1, texto="ORA-01031: insufficient privileges"))

    respuesta = cliente.get("/base/estado")

    assert respuesta.status_code == 500
    assert respuesta.json()["log"] == "ORA-01031: insufficient privileges"


def test_herramienta_no_disponible_responde_500_con_mensaje(cliente):
    class SinSqlplus(EntornoFalso):
        def ejecutar(self, comando):
            raise HerramientaNoDisponible("sqlplus")

    usar(SinSqlplus())

    for respuesta in (cliente.get("/base/estado"), cliente.post("/base/estado", json={"accion": "APAGAR"})):
        assert respuesta.status_code == 500
        assert "sqlplus" in respuesta.json()["mensaje"]


def test_el_sid_por_defecto_es_xe(cliente, monkeypatch):
    monkeypatch.delenv("ORACLE_SID", raising=False)
    entorno = en_estado("OPEN")

    cliente.get("/base/estado")

    assert entorno.herramientas[0]["variables"] == {"ORACLE_SID": "XE"}


def test_el_sid_sale_de_oracle_sid(cliente, monkeypatch):
    monkeypatch.setenv("ORACLE_SID", "ORCLCDB")
    entorno = en_estado("OPEN", Salida(0, "ok"))

    cliente.post("/base/estado", json={"accion": "APAGAR"})

    assert [h["variables"] for h in entorno.herramientas] == [{"ORACLE_SID": "ORCLCDB"}] * 2
