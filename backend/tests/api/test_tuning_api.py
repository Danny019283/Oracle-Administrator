import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, obtener_sesion

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}
MB = 1024 * 1024


class ConsultaFalsa:
    def __call__(self, sql, params=None):
        if "dba_users" in sql:
            return [("HR",)]
        if "dba_tablespaces" in sql:
            return [("USERS", "PERMANENT", "ONLINE", "NO", 100 * MB, 100 * MB, 25 * MB, 1)]
        if "dba_tab_statistics" in sql:
            return [("EMPLOYEES", 107, 5, 69, "20/10/2026 08:00:00", "NO")]
        if "dba_tab_columns" in sql:
            return [("EMPLOYEE_ID", "NUMBER"), ("LAST_NAME", "VARCHAR2")]
        if "dba_indexes" in sql:
            return [
                ("HR", "EMP_EMP_ID_PK", "UNIQUE", "NORMAL", "VALID", "USERS", None, 107, 0, "EMPLOYEE_ID", "EMP_EMP_ID_PK"),
                ("HR", "EMP_NAME_IX", "NONUNIQUE", "NORMAL", "VALID", "USERS", None, 102, 0, "LAST_NAME", None),
            ]
        return []


class SentenciaFalsa:
    def __init__(self, error=None):
        self.llamadas = []
        self.error = error

    @property
    def sqls(self):
        return [sql for sql, _ in self.llamadas]

    def __call__(self, sql, params=None):
        if self.error:
            raise oracledb.DatabaseError(self.error)
        self.llamadas.append((sql, params))


class SesionFalsa:
    def __init__(self, error=None):
        self.pasos = []
        self.error = error

    def __call__(self, pasos):
        if self.error:
            raise oracledb.DatabaseError(self.error)
        self.pasos = list(pasos)
        return [None] * (len(pasos) - 2) + [
            [("Plan hash value: 1",)],
            [(0, None, 0, "SELECT STATEMENT", None, None, None, 2, 1, 13, None, None)],
        ]


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(sentencia=None, sesion=None):
    sentencia = sentencia or SentenciaFalsa()
    sesion = sesion or SesionFalsa()
    app.dependency_overrides[obtener_consulta_admin] = lambda: ConsultaFalsa()
    app.dependency_overrides[obtener_sentencia] = lambda: sentencia
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    return sentencia, sesion


def test_catalogos(cliente):
    usar()

    respuesta = cliente.get("/tuning/catalogos", headers=CABECERAS)

    assert respuesta.json() == {"schemas": ["HR"], "tablespaces": ["USERS"]}


def test_plan_de_ejecucion_en_un_schema(cliente):
    _, sesion = usar()

    respuesta = cliente.post(
        "/tuning/plan", json={"sql": "SELECT * FROM dual", "schema": "HR"}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["texto"] == ["Plan hash value: 1"]
    assert respuesta.json()["operaciones"][0]["operacion"] == "SELECT STATEMENT"
    assert sesion.pasos[0] == ("ALTER SESSION SET CURRENT_SCHEMA = HR", None)


def test_plan_de_sentencia_no_permitida_responde_422(cliente):
    _, sesion = usar()

    respuesta = cliente.post("/tuning/plan", json={"sql": "DROP TABLE x"}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"]
    assert sesion.pasos == []


def test_plan_con_error_de_sintaxis_lo_explica(cliente):
    usar(sesion=SesionFalsa(error="ORA-00904: \"SALARIO\": invalid identifier"))

    respuesta = cliente.post("/tuning/plan", json={"sql": "SELECT salario FROM dual"}, headers=CABECERAS)

    assert respuesta.status_code == 500
    assert "columna" in respuesta.json()["explicacion"]


def test_tablas_con_estadisticas(cliente):
    usar()

    respuesta = cliente.get("/tuning/tablas", params={"schema": "HR"}, headers=CABECERAS)

    assert respuesta.json()["tablas"][0]["tabla"] == "EMPLOYEES"


def test_schema_interno_responde_404(cliente):
    usar()

    respuesta = cliente.get("/tuning/tablas", params={"schema": "SYS"}, headers=CABECERAS)

    assert respuesta.status_code == 404


def test_recolectar_estadisticas_de_tabla(cliente):
    sentencia, _ = usar()

    respuesta = cliente.post(
        "/tuning/estadisticas", json={"schema": "HR", "tabla": "EMPLOYEES"}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Estadísticas de HR.EMPLOYEES actualizadas"}
    assert sentencia.llamadas[0][1] == {"schema": "HR", "tabla": "EMPLOYEES"}


def test_indices_y_columnas_de_una_tabla(cliente):
    usar()

    respuesta = cliente.get(
        "/tuning/indices", params={"schema": "HR", "tabla": "EMPLOYEES"}, headers=CABECERAS
    )

    assert [i["nombre"] for i in respuesta.json()["indices"]] == ["EMP_EMP_ID_PK", "EMP_NAME_IX"]
    assert [c["nombre"] for c in respuesta.json()["columnas"]] == ["EMPLOYEE_ID", "LAST_NAME"]


def test_crear_indice(cliente):
    sentencia, _ = usar()

    respuesta = cliente.post(
        "/tuning/indices",
        json={"schema": "HR", "tabla": "EMPLOYEES", "nombre": "emp_ix", "columnas": ["LAST_NAME"]},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Índice HR.EMP_IX creado"}
    assert sentencia.sqls == ["CREATE INDEX HR.EMP_IX ON HR.EMPLOYEES (LAST_NAME)"]


def test_eliminar_indice_exige_confirmacion(cliente):
    sentencia, _ = usar()

    respuesta = cliente.post(
        "/tuning/indices/eliminar",
        json={"schema": "HR", "tabla": "EMPLOYEES", "nombre": "EMP_NAME_IX"},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 422
    assert sentencia.sqls == []


def test_eliminar_indice_confirmado(cliente):
    sentencia, _ = usar()

    respuesta = cliente.post(
        "/tuning/indices/eliminar",
        json={"schema": "HR", "tabla": "EMPLOYEES", "nombre": "EMP_NAME_IX", "confirmar": True},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert sentencia.sqls == ["DROP INDEX HR.EMP_NAME_IX"]


def test_no_elimina_indice_de_llave_primaria(cliente):
    sentencia, _ = usar()

    respuesta = cliente.post(
        "/tuning/indices/eliminar",
        json={"schema": "HR", "tabla": "EMPLOYEES", "nombre": "EMP_EMP_ID_PK", "confirmar": True},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 422
    assert "EMP_EMP_ID_PK" in respuesta.json()["errores"][0]
    assert sentencia.sqls == []
