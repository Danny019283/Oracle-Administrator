import pytest

from src.services.tablas import SinTablas, listar_tablas


class ConsultaFalsa:
    def __init__(self, filas):
        self.filas = filas
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql.lower())
        return self.filas


def test_devuelve_los_nombres_de_las_tablas_del_usuario():
    consulta = ConsultaFalsa([("CLIENTES",), ("PEDIDOS",)])

    assert listar_tablas(consulta) == ["CLIENTES", "PEDIDOS"]


def test_consulta_solo_las_tablas_del_usuario_conectado():
    consulta = ConsultaFalsa([("CLIENTES",)])

    listar_tablas(consulta)

    assert len(consulta.sqls) == 1
    assert "user_tables" in consulta.sqls[0]
    assert "dba_tables" not in consulta.sqls[0]
    assert "all_tables" not in consulta.sqls[0]


def test_sin_tablas_informa_que_no_hay_tablas_en_el_schema():
    with pytest.raises(SinTablas, match="No hay tablas en el schema"):
        listar_tablas(ConsultaFalsa([]))
