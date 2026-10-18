from src.services.expdp_runner import Conexion
from src.services.oracle_conexion import consulta_oracle


class CursorFalso:
    def __init__(self, filas, registro):
        self.filas = filas
        self.registro = registro

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.registro.append((sql, params))

    def fetchall(self):
        return self.filas


class ConexionBDFalsa:
    def __init__(self, filas, registro):
        self.filas = filas
        self.registro = registro

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return CursorFalso(self.filas, self.registro)


class DriverFalso:
    AUTH_MODE_DEFAULT = "default"
    AUTH_MODE_SYSDBA = "sysdba"

    def __init__(self, filas=(("HR",),)):
        self.filas = list(filas)
        self.argumentos = None
        self.ejecutado = []

    def connect(self, **kwargs):
        self.argumentos = kwargs
        return ConexionBDFalsa(self.filas, self.ejecutado)


def conexion(**cambios):
    datos = dict(
        usuario="HR",
        password="s3creta!",
        servicio="XEPDB1",
        host="db.sesion",
        puerto=1555,
        sysdba=False,
    )
    return Conexion(**{**datos, **cambios})


def test_conecta_al_host_y_puerto_de_la_conexion():
    driver = DriverFalso()

    consulta_oracle(conexion(), driver)("select 1 from dual")

    assert driver.argumentos == {
        "user": "HR",
        "password": "s3creta!",
        "dsn": "db.sesion:1555/XEPDB1",
        "mode": "default",
    }


def test_conecta_como_sysdba_cuando_la_conexion_lo_indica():
    driver = DriverFalso()

    consulta_oracle(conexion(sysdba=True), driver)("select 1 from dual")

    assert driver.argumentos["mode"] == "sysdba"


def test_ejecuta_la_consulta_con_sus_parametros_y_devuelve_las_filas():
    driver = DriverFalso(filas=[("A",), ("B",)])

    filas = consulta_oracle(conexion(), driver)("select x from t where y = :y", {"y": 1})

    assert filas == [("A",), ("B",)]
    assert driver.ejecutado == [("select x from t where y = :y", {"y": 1})]


def test_sin_parametros_ejecuta_con_un_diccionario_vacio():
    driver = DriverFalso()

    consulta_oracle(conexion(), driver)("select 1 from dual")

    assert driver.ejecutado == [("select 1 from dual", {})]


def test_sin_host_ni_puerto_explicitos_usa_los_del_entorno(monkeypatch):
    monkeypatch.setenv("ORACLE_HOST", "host.env")
    monkeypatch.setenv("ORACLE_PORT", "1999")
    driver = DriverFalso()

    consulta_oracle(Conexion(usuario="HR", password="x", servicio="S"), driver)("select 1")

    assert driver.argumentos["dsn"] == "host.env:1999/S"
