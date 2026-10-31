import dataclasses
from datetime import datetime

import oracledb
import pytest

from src.services import respaldos_programados as rp

COLUMNAS = [
    "ID", "NOMBRE", "POLITICA", "FRECUENCIA", "HORA", "DIA", "INTERVALO_HORAS",
    "DIRECTORIO", "RUTA_SCRIPT", "RUTA_RMAN", "ENTORNO", "TAREA", "CREADO",
    "ULTIMA_EJECUCION", "ULTIMO_RESULTADO",
]


class Sentencia:
    def __init__(self, error=None):
        self.llamadas = []
        self.error = error

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        if self.error:
            raise self.error


class Consulta:
    def __init__(self, filas=None, error=None):
        self.llamadas = []
        self.filas = filas or []
        self.error = error

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        if self.error:
            raise self.error
        return self.filas


def fila(id_=1, nombre="diario"):
    return (id_, nombre, "FULL", "DIARIO", "02:00", None, None, "DIR_RESP",
            "/r/s.sh", "/r/s.rman", "contenedor", "OracleAdmin_1",
            datetime(2026, 1, 1), None, None)


def ora(codigo):
    return oracledb.DatabaseError(f"{codigo}: error simulado")


def test_asegurar_tabla_crea_con_las_15_columnas():
    s = Sentencia()
    rp.asegurar_tabla(s)
    sql = s.llamadas[0][0]
    assert sql.startswith("CREATE TABLE SYSTEM.RESPALDOS_PROGRAMADOS")
    for columna in COLUMNAS:
        assert columna in sql
    assert "VARCHAR2(5)" in sql and "SYSTIMESTAMP" in sql


def test_asegurar_tabla_ignora_ora_00955():
    rp.asegurar_tabla(Sentencia(error=ora("ORA-00955")))


def test_asegurar_tabla_propaga_otros_errores():
    with pytest.raises(oracledb.DatabaseError):
        rp.asegurar_tabla(Sentencia(error=ora("ORA-01031")))


def test_insertar_usa_binds_y_devuelve_id():
    s, c = Sentencia(), Consulta(filas=[(7,)])
    nombre = "x'; DROP TABLE y;--"
    nuevo = rp.insertar(
        s, c, nombre=nombre, politica="FULL", frecuencia="DIARIO", hora="02:00",
        dia=None, intervalo_horas=None, directorio="DIR", ruta_script="/s.sh",
        ruta_rman="/s.rman", entorno="local", tarea="t",
    )
    assert nuevo == 7
    sql, params = s.llamadas[0]
    assert sql.startswith("INSERT INTO SYSTEM.RESPALDOS_PROGRAMADOS")
    assert nombre not in sql and "DIARIO" not in sql and "02:00" not in sql
    assert params["nombre"] == nombre and params["hora"] == "02:00"
    assert params["dia"] is None
    assert c.llamadas[0][1] == {"nombre": nombre}
    assert nombre not in c.llamadas[0][0]


def test_listar_mapea_y_ordena():
    c = Consulta(filas=[fila(1), fila(2, "b")])
    r = rp.listar(c)
    assert "ORDER BY ID" in c.llamadas[0][0]
    assert [x.id for x in r] == [1, 2]
    assert r[0].nombre == "diario" and r[0].ruta_rman == "/r/s.rman"
    assert [f.name for f in dataclasses.fields(r[0])] == [x.lower() for x in COLUMNAS]
    with pytest.raises(dataclasses.FrozenInstanceError):
        r[0].nombre = "otro"


def test_listar_tabla_inexistente_devuelve_vacio():
    assert rp.listar(Consulta(error=ora("ORA-00942"))) == []


def test_listar_propaga_otros_errores():
    with pytest.raises(oracledb.DatabaseError):
        rp.listar(Consulta(error=ora("ORA-01031")))


def test_obtener_presente_ausente_y_tabla_inexistente():
    c = Consulta(filas=[fila(3)])
    assert rp.obtener(c, 3).id == 3
    assert c.llamadas[0][1] == {"id": 3}
    assert "3" not in c.llamadas[0][0]
    assert rp.obtener(Consulta(), 3) is None
    assert rp.obtener(Consulta(error=ora("ORA-00942")), 3) is None


def test_actualizar_resultado_con_binds():
    s = Sentencia()
    rp.actualizar_resultado(s, 4, "Completo")
    sql, params = s.llamadas[0]
    assert sql.startswith("UPDATE SYSTEM.RESPALDOS_PROGRAMADOS")
    assert "ULTIMA_EJECUCION = SYSTIMESTAMP" in sql and "Completo" not in sql
    assert params == {"id": 4, "resultado": "Completo"}


def test_eliminar_fila_con_bind():
    s = Sentencia()
    rp.eliminar_fila(s, 5)
    sql, params = s.llamadas[0]
    assert sql.startswith("DELETE FROM SYSTEM.RESPALDOS_PROGRAMADOS")
    assert params == {"id": 5}
