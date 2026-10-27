import oracledb
import pytest

from src.services.expdp_runner import Conexion
from src.services.oracle_ejecucion import sentencia_oracle, sesion_oracle


class ConexionFalsa:
    def __init__(self, registro):
        self.registro = registro

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return CursorFalso(self.registro)

    def commit(self):
        self.registro["commit"] = True


class CursorFalso:
    def __init__(self, registro):
        self.registro = registro
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.registro["sql"] = sql
        self.registro.setdefault("pasos", []).append((sql, params))
        self.registro["params"] = params
        # Solo las consultas (SELECT) devuelven filas.
        self.description = [("COLUMNA",)] if sql.lstrip().upper().startswith("SELECT") else None

    def fetchall(self):
        return [("fila",)]


@pytest.fixture
def registro(monkeypatch):
    registro = {}

    def conectar(**argumentos):
        registro["conexion"] = argumentos
        return ConexionFalsa(registro)

    monkeypatch.setattr(oracledb, "connect", conectar)
    return registro


def test_ejecuta_con_el_host_el_puerto_y_el_servicio_de_la_sesion(registro, monkeypatch):
    monkeypatch.setenv("ORACLE_HOST", "otro-host")
    monkeypatch.setenv("ORACLE_PORT", "9999")
    conexion = Conexion(
        usuario="HR", password="s3creta!", servicio="XEPDB1", host="db.sesion", puerto=1555
    )

    sentencia_oracle(conexion)("ALTER USER X ACCOUNT LOCK")

    assert registro["conexion"]["user"] == "HR"
    assert registro["conexion"]["password"] == "s3creta!"
    assert registro["conexion"]["dsn"] == "db.sesion:1555/XEPDB1"
    assert registro["sql"] == "ALTER USER X ACCOUNT LOCK"
    assert registro["commit"] is True


@pytest.mark.parametrize(
    "sysdba, modo",
    [(True, oracledb.AUTH_MODE_SYSDBA), (False, oracledb.AUTH_MODE_DEFAULT)],
)
def test_conecta_como_sysdba_solo_si_la_sesion_lo_es(registro, sysdba, modo):
    conexion = Conexion(usuario="SYS", password="x", servicio="XE", sysdba=sysdba)

    sentencia_oracle(conexion)("ALTER SYSTEM CHECKPOINT")

    assert registro["conexion"]["mode"] == modo


def test_la_sesion_de_varios_pasos_usa_el_host_el_puerto_y_el_servicio_de_la_sesion(registro, monkeypatch):
    monkeypatch.setenv("ORACLE_HOST", "otro-host")
    monkeypatch.setenv("ORACLE_PORT", "9999")
    conexion = Conexion(
        usuario="HR", password="s3creta!", servicio="XEPDB1", host="db.sesion", puerto=1555
    )

    sesion_oracle(conexion)([("EXPLAIN PLAN FOR SELECT 1 FROM dual", None)])

    assert registro["conexion"]["user"] == "HR"
    assert registro["conexion"]["password"] == "s3creta!"
    assert registro["conexion"]["dsn"] == "db.sesion:1555/XEPDB1"


@pytest.mark.parametrize(
    "sysdba, modo",
    [(True, oracledb.AUTH_MODE_SYSDBA), (False, oracledb.AUTH_MODE_DEFAULT)],
)
def test_la_sesion_de_varios_pasos_conecta_como_sysdba_solo_si_la_sesion_lo_es(registro, sysdba, modo):
    conexion = Conexion(usuario="SYS", password="x", servicio="XE", sysdba=sysdba)

    sesion_oracle(conexion)([("SELECT 1 FROM dual", None)])

    assert registro["conexion"]["mode"] == modo


def test_la_sesion_de_varios_pasos_ejecuta_todo_en_una_conexion_y_devuelve_las_filas(registro):
    conexion = Conexion(usuario="HR", password="x", servicio="XEPDB1")

    resultados = sesion_oracle(conexion)(
        [
            ("EXPLAIN PLAN FOR SELECT 1 FROM dual", None),
            ("SELECT plan_table_output FROM TABLE(dbms_xplan.display())", {"x": 1}),
        ]
    )

    assert [sql for sql, _ in registro["pasos"]] == [
        "EXPLAIN PLAN FOR SELECT 1 FROM dual",
        "SELECT plan_table_output FROM TABLE(dbms_xplan.display())",
    ]
    assert resultados == [None, [("fila",)]]
