from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services.directorios import (
    Directorio,
    DirectorioInvalido,
    DirectorioNoEncontrado,
    SinDirectorios,
    ejemplos_ruta,
    listar_directorios,
    listar_todos_directorios,
    validar_ruta,
)


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


def test_listar_todos_devuelve_todos_sin_filtrar_por_grants_y_ordenados():
    consulta = ConsultaFalsa([("A_DIR", "/a"), ("B_DIR", "/b")])

    assert listar_todos_directorios(consulta) == [
        Directorio(nombre="A_DIR", ruta="/a"),
        Directorio(nombre="B_DIR", ruta="/b"),
    ]
    sql = consulta.sqls[0]
    assert "all_directories" in sql
    assert "all_tab_privs" not in sql
    assert "order by" in sql


def test_listar_todos_sin_filas_devuelve_lista_vacia():
    assert listar_todos_directorios(ConsultaFalsa([])) == []


@pytest.mark.parametrize(
    "ruta, tipo",
    [
        ("/opt/oracle/respaldos", PurePosixPath),
        ("C:\\respaldos", PureWindowsPath),
        ("\\\\servidor\\recurso", PureWindowsPath),
    ],
)
def test_validar_ruta_acepta_rutas_absolutas_del_tipo(ruta, tipo):
    assert validar_ruta(ruta, tipo) == []


@pytest.mark.parametrize(
    "ruta, tipo",
    [
        ("", PurePosixPath),
        ("C:\\respaldos", PurePosixPath),
        ("respaldos", PurePosixPath),
        ("respaldos", PureWindowsPath),
        ("/" + "a" * 4000, PurePosixPath),
        ("/opt/o'racle", PurePosixPath),
        ("/opt/a\nb", PurePosixPath),
        ("/opt/a\x00b", PurePosixPath),
    ],
)
def test_validar_ruta_rechaza_rutas_invalidas(ruta, tipo):
    assert validar_ruta(ruta, tipo)


def test_ejemplos_ruta_segun_tipo():
    assert ejemplos_ruta(PurePosixPath) == ["/opt/oracle/respaldos"]
    assert ejemplos_ruta(PureWindowsPath) == ["C:\\respaldos", "\\\\servidor\\recurso"]


def test_excepciones_de_directorio():
    assert DirectorioInvalido(["a", "b"]).errores == ["a", "b"]
    assert str(DirectorioInvalido(["a", "b"])) == "a; b"
    assert issubclass(DirectorioNoEncontrado, Exception)
