import pytest

from src.services.directorios import Directorio, SinDirectorios, listar_directorios


class ConsultaFalsa:
    def __init__(self, filas):
        self.filas = filas
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql.lower())
        return self.filas


def test_devuelve_nombre_y_ruta_fisica_de_cada_directorio():
    consulta = ConsultaFalsa(
        [("RESPALDO", "/opt/oracle/Respaldos"), ("DATA_PUMP_DIR", "/opt/oracle/dpdump")]
    )

    assert listar_directorios(consulta) == [
        Directorio(nombre="RESPALDO", ruta="/opt/oracle/Respaldos"),
        Directorio(nombre="DATA_PUMP_DIR", ruta="/opt/oracle/dpdump"),
    ]


def test_solo_considera_directorios_con_read_y_write_concedidos():
    consulta = ConsultaFalsa([("RESPALDO", "/opt/oracle/Respaldos")])

    listar_directorios(consulta)

    assert len(consulta.sqls) == 1
    sql = consulta.sqls[0]
    assert "all_directories" in sql
    assert "all_tab_privs" in sql
    assert "'read'" in sql
    assert "'write'" in sql


def test_sin_directorios_informa_y_sugiere_crear_uno():
    with pytest.raises(SinDirectorios) as error:
        listar_directorios(ConsultaFalsa([]))

    mensaje = str(error.value)
    assert "No hay directorios disponibles" in mensaje
    assert "crear" in mensaje.lower()
