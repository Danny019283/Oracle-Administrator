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
CARPETA = "/opt/oracle/oradata/XE/XEPDB1/"


class ConsultaFalsa:
    def __call__(self, sql, params=None):
        if "dba_tablespaces" in sql:
            return [
                ("SYSTEM", "PERMANENT", "ONLINE", "NO", 300 * MB, 300 * MB, 10 * MB, 1),
                ("USERS", "PERMANENT", "ONLINE", "NO", 100 * MB, 100 * MB, 25 * MB, 1),
            ]
        if "INSTR(file_name" in sql:
            return [(CARPETA,)]
        if "dba_data_files" in sql:
            return [(7, CARPETA + "users01.dbf", 100 * MB, "NO", 0, "AVAILABLE")]
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


def test_lista_tablespaces_y_la_carpeta_de_datafiles(cliente):
    usar()

    respuesta = cliente.get("/tablespaces", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json()["carpeta"] == CARPETA
    assert [t["nombre"] for t in respuesta.json()["tablespaces"]] == ["SYSTEM", "USERS"]
    assert respuesta.json()["tablespaces"][1]["porcentaje_uso"] == 75.0


def test_detalle_de_tablespace(cliente):
    usar()

    respuesta = cliente.get("/tablespaces/users", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json()["datafiles"][0]["id"] == 7


def test_tablespace_inexistente_responde_404(cliente):
    usar()

    respuesta = cliente.get("/tablespaces/NOEXISTE", headers=CABECERAS)

    assert respuesta.status_code == 404


def test_crear_tablespace(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/tablespaces",
        json={"nombre": "ventas", "tipo": "PERMANENT", "archivo": "ventas01.dbf", "tamano": "100M"},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Tablespace VENTAS creado"}
    assert sentencia.sqls == [
        f"CREATE TABLESPACE VENTAS DATAFILE '{CARPETA}ventas01.dbf' SIZE 100M "
        "AUTOEXTEND ON NEXT 10M MAXSIZE UNLIMITED"
    ]


def test_crear_tablespace_invalido_responde_422_con_los_errores(cliente):
    sentencia = usar()

    respuesta = cliente.post("/tablespaces", json={"nombre": "", "archivo": ""}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert len(respuesta.json()["errores"]) == 2
    assert sentencia.sqls == []


def test_si_oracle_rechaza_explica_el_error(cliente):
    usar(SentenciaFalsa(error="ORA-01543: tablespace 'VENTAS' already exists"))

    respuesta = cliente.post(
        "/tablespaces",
        json={"nombre": "ventas", "archivo": "ventas01.dbf", "tamano": "100M"},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 500
    assert respuesta.json()["explicacion"] == "Ya existe un tablespace con ese nombre"
    assert respuesta.json()["error"].startswith("ORA-01543")


def test_agregar_datafile(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/tablespaces/USERS/archivos",
        json={"archivo": "users02.dbf", "tamano": "50M", "autoextend": False},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Archivo users02.dbf agregado a USERS"}
    assert sentencia.sqls[0].startswith("ALTER TABLESPACE USERS ADD DATAFILE")


def test_redimensionar_datafile(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/tablespaces/USERS/archivos/7/redimensionar", json={"tamano": "200M"}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert sentencia.sqls == ["ALTER DATABASE DATAFILE 7 RESIZE 200M"]


def test_autoextend_de_datafile(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/tablespaces/USERS/archivos/7/autoextend", json={"autoextend": False}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert sentencia.sqls == ["ALTER DATABASE DATAFILE 7 AUTOEXTEND OFF"]


def test_offline_exige_confirmacion(cliente):
    sentencia = usar()

    respuesta = cliente.post("/tablespaces/USERS/estado", json={"estado": "OFFLINE"}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert sentencia.sqls == []


def test_offline_confirmado(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/tablespaces/USERS/estado", json={"estado": "OFFLINE", "confirmar": True}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert sentencia.sqls == ["ALTER TABLESPACE USERS OFFLINE NORMAL"]


def test_read_only_no_necesita_confirmacion(cliente):
    sentencia = usar()

    respuesta = cliente.post("/tablespaces/USERS/estado", json={"estado": "READ ONLY"}, headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Tablespace USERS ahora está READ ONLY"}
    assert sentencia.sqls == ["ALTER TABLESPACE USERS READ ONLY"]


def test_no_cambia_el_estado_de_system(cliente):
    sentencia = usar()

    respuesta = cliente.post(
        "/tablespaces/SYSTEM/estado", json={"estado": "OFFLINE", "confirmar": True}, headers=CABECERAS
    )

    assert respuesta.status_code == 422
    assert sentencia.sqls == []
