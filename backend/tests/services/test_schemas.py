import pytest

from src.services.schemas import SinSchemas, listar_schemas


class ConsultaFalsa:
    def __init__(self, filas):
        self.filas = filas
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql.lower())
        return self.filas


def test_devuelve_los_nombres_de_los_schemas_de_usuario():
    consulta = ConsultaFalsa([("HR",), ("VENTAS",)])

    assert listar_schemas(consulta) == ["HR", "VENTAS"]


def test_excluye_los_schemas_mantenidos_por_oracle():
    consulta = ConsultaFalsa([("HR",)])

    listar_schemas(consulta)

    assert len(consulta.sqls) == 1
    assert "all_users" in consulta.sqls[0]
    assert "oracle_maintained = 'n'" in consulta.sqls[0]


def test_sin_schemas_informa_que_no_hay_schemas_de_usuario():
    with pytest.raises(SinSchemas, match="No hay schemas de usuario"):
        listar_schemas(ConsultaFalsa([]))
