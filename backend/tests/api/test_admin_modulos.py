import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}
MB = 1024 * 1024


class ConsultaFalsa:
    def __call__(self, sql, params=None):
        if "v$instance" in sql:
            return [("XE", "srv", "21.3.0.0.0", "OPEN", "20/10/2026 08:00:00", "XE", "ARCHIVELOG", "READ WRITE")]
        if "v$sga" in sql:
            return [("Fixed Size", 10 * MB)]
        if "v$pgastat" in sql:
            return [("total PGA allocated", 100 * MB)]
        if "v$sysstat" in sql:
            return [(5, 100)]
        if "v$librarycache" in sql:
            return [(90, 100)]
        if "COUNT(*)" in sql:
            return [(3, 1)]
        if "v$session" in sql:
            return [(25, 101, "HR", "ACTIVE", "emijo", "PC", "sqlplus.exe", "24/10/2026", "abc")]
        if "audit_unified_enabled_policies" in sql:
            return []
        if "audit_unified_policies" in sql:
            return [("AUD_EMP", "DELETE", "HR", "EMPLOYEES")]
        if "dba_users" in sql:
            return [("HR", "OPEN", "USERS", "TEMP", "DEFAULT", "01/10/2026")]
        if "dba_tablespaces" in sql:
            return [("USERS", "PERMANENT"), ("TEMP", "TEMPORARY")]
        if "dba_roles" in sql:
            return [("CONNECT",)]
        if "system_privilege_map" in sql:
            return [("CREATE SESSION",)]
        return []


class SentenciaFalsa:
    def __init__(self, error=None):
        self.sqls = []
        self.error = error

    def __call__(self, sql, params=None):
        if self.error:
            raise oracledb.DatabaseError(self.error)
        self.sqls.append(sql)


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(sentencia=None):
    sentencia = sentencia or SentenciaFalsa()
    app.dependency_overrides[obtener_consulta_admin] = lambda: ConsultaFalsa()
    app.dependency_overrides[obtener_sentencia] = lambda: sentencia
    return sentencia


def test_resumen_de_performance(cliente):
    usar()

    respuesta = cliente.get("/performance/resumen", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json()["indicadores"]["buffer_cache_hit"] == 95.0
    assert respuesta.json()["memoria"]["sga_total_mb"] == 10.0


def test_terminar_sesion_exige_confirmacion(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/performance/sesiones/terminar", json={"sid": 25, "serial": 101}, headers=CABECERAS
    )

    assert respuesta.status_code == 422
    assert sentencia.sqls == []


def test_terminar_sesion_confirmada(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/performance/sesiones/terminar",
        json={"sid": 25, "serial": 101, "confirmar": True},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert sentencia.sqls == ["ALTER SYSTEM KILL SESSION '25,101' IMMEDIATE"]


def test_lista_politicas_de_auditoria(cliente):
    usar()

    respuesta = cliente.get("/auditoria/politicas", headers=CABECERAS)

    assert respuesta.json()["politicas"][0]["nombre"] == "AUD_EMP"


def test_crear_politica_invalida_responde_422(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/auditoria/politicas", json={"nombre": "", "tipo": "tabla"}, headers=CABECERAS
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"]
    assert sentencia.sqls == []


def test_si_oracle_rechaza_responde_500_con_explicacion(cliente):
    usar(SentenciaFalsa(error="ORA-01031: privilegios insuficientes"))

    respuesta = cliente.post(
        "/auditoria/politicas",
        json={"nombre": "AUD_X", "tipo": "sesion", "acciones": ["LOGON"]},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["error"].startswith("ORA-01031")
    assert "privilegios" in cuerpo["explicacion"]


def test_crear_usuario_no_devuelve_la_password(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/seguridad/usuarios",
        json={"usuario": "ventas", "password": "Clave#Secreta1", "tablespace": "USERS", "temporal": "TEMP"},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Usuario VENTAS creado"}
    assert "Clave#Secreta1" not in respuesta.text
    assert sentencia.sqls[-1] == "GRANT CREATE SESSION TO VENTAS"


def test_usuario_interno_responde_404(cliente):
    usar()

    respuesta = cliente.get("/seguridad/usuarios/SYS", headers=CABECERAS)

    assert respuesta.status_code == 404


def test_eliminar_usuario_exige_confirmacion(cliente):
    sentencia = usar()

    respuesta = cliente.post("/seguridad/usuarios/HR/eliminar", json={}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert sentencia.sqls == []


def test_otorgar_rol(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/seguridad/usuarios/HR/roles", json={"nombre": "connect", "otorgar": True}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert sentencia.sqls == ["GRANT CONNECT TO HR"]
