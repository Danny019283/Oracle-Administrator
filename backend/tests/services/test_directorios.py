from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services.entorno_oracle import OperacionEntornoFallida
from tests.services.entorno_falso import EntornoFalso

from src.services.directorios import (
    Directorio,
    DirectorioInvalido,
    DirectorioNoEncontrado,
    SinDirectorios,
    crear_directorio,
    editar_directorio,
    eliminar_directorio,
    ejemplos_ruta,
    listar_directorios,
    listar_todos_directorios,
    validar_ruta,
)


class ConsultaFalsa:
    def __init__(self, filas, schemas=()):
        self.filas = filas
        self.schemas = schemas
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql.lower())
        if "all_users" in sql.lower():
            return [(params["schema"],)] if params["schema"] in self.schemas else []
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


class SentenciaFalsa:
    def __init__(self):
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)


def test_crear_directorio_con_schema_da_permisos_y_ejecuta_create_y_grant_al_schema_en_orden():
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()

    nombre = crear_directorio(
        ConsultaFalsa([], schemas=["HR"]), sentencia, entorno, "respaldo", "/opt/oracle/respaldos", "hr"
    )

    assert nombre == "RESPALDO"
    assert entorno.permisos == ["/opt/oracle/respaldos"]
    assert sentencia.sqls == [
        "CREATE DIRECTORY RESPALDO AS '/opt/oracle/respaldos'",
        "GRANT READ, WRITE ON DIRECTORY RESPALDO TO HR",
    ]


@pytest.mark.parametrize("schema", [None, ""])
def test_crear_directorio_sin_schema_no_ejecuta_ningun_grant(schema):
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()
    consulta = ConsultaFalsa([])

    crear_directorio(consulta, sentencia, entorno, "respaldo", "/opt/oracle/respaldos", schema)

    assert entorno.permisos == ["/opt/oracle/respaldos"]
    assert sentencia.sqls == ["CREATE DIRECTORY RESPALDO AS '/opt/oracle/respaldos'"]
    assert not any("all_users" in sql for sql in consulta.sqls)


@pytest.mark.parametrize(
    "schema, texto", [("1mal", "schema"), ("hr", "HR")]
)
def test_crear_directorio_con_schema_invalido_o_inexistente_no_toca_entorno_ni_sentencias(schema, texto):
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()

    with pytest.raises(DirectorioInvalido) as error:
        crear_directorio(ConsultaFalsa([]), sentencia, entorno, "respaldo", "/opt/r", schema)

    assert texto in str(error.value)
    assert entorno.permisos == [] and sentencia.sqls == []


def test_crear_directorio_comprueba_duplicado_en_all_directories_sin_grants():
    consulta = ConsultaFalsa([("RESPALDO", "/x")])
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()

    with pytest.raises(DirectorioInvalido):
        crear_directorio(consulta, sentencia, entorno, "respaldo", "/opt/r")

    assert "all_directories" in consulta.sqls[0]
    assert "all_tab_privs" not in consulta.sqls[0]
    assert entorno.permisos == [] and sentencia.sqls == []


@pytest.mark.parametrize(
    "nombre, ruta, texto",
    [("1mal", "/opt/r", "nombre"), ("ok", "relativa", "absoluta"), ("", "", "obligatori")],
)
def test_crear_directorio_invalido_no_toca_entorno_ni_sentencias(nombre, ruta, texto):
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()

    with pytest.raises(DirectorioInvalido) as error:
        crear_directorio(ConsultaFalsa([]), sentencia, entorno, nombre, ruta)

    assert texto in str(error.value)
    assert entorno.permisos == [] and sentencia.sqls == []


def test_crear_directorio_valida_la_ruta_con_el_tipo_del_entorno():
    entorno = EntornoFalso()
    entorno.tipo_ruta = PureWindowsPath

    crear_directorio(ConsultaFalsa([]), SentenciaFalsa(), entorno, "r", "C:\\respaldos")

    assert entorno.permisos == ["C:\\respaldos"]


def test_crear_directorio_si_fallan_los_permisos_no_ejecuta_sentencias():
    entorno = EntornoFalso(fallo_permisos="chown: no such file")
    sentencia = SentenciaFalsa()

    with pytest.raises(OperacionEntornoFallida):
        crear_directorio(ConsultaFalsa([]), sentencia, entorno, "r", "/opt/r")

    assert sentencia.sqls == []


def test_editar_directorio_da_permisos_y_ejecuta_solo_create_or_replace():
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()

    editar_directorio(ConsultaFalsa([("RESPALDO", "/x")]), sentencia, entorno, "respaldo", "/opt/nueva")

    assert entorno.permisos == ["/opt/nueva"]
    assert sentencia.sqls == ["CREATE OR REPLACE DIRECTORY RESPALDO AS '/opt/nueva'"]


def test_editar_directorio_valida_la_ruta_con_el_tipo_del_entorno():
    entorno = EntornoFalso()
    entorno.tipo_ruta = PureWindowsPath

    editar_directorio(ConsultaFalsa([("R", "x")]), SentenciaFalsa(), entorno, "r", "C:\\respaldos")

    assert entorno.permisos == ["C:\\respaldos"]


@pytest.mark.parametrize(
    "nombre, ruta, filas, excepcion",
    [
        ("r", "relativa", [("R", "/x")], DirectorioInvalido),
        ("1mal", "/opt/r", [("R", "/x")], DirectorioInvalido),
        ("otro", "/opt/r", [("R", "/x")], DirectorioNoEncontrado),
        ("data_pump_dir", "/opt/r", [("DATA_PUMP_DIR", "/x")], DirectorioInvalido),
    ],
)
def test_editar_directorio_con_error_no_toca_entorno_ni_sentencias(nombre, ruta, filas, excepcion):
    entorno = EntornoFalso()
    sentencia = SentenciaFalsa()

    with pytest.raises(excepcion):
        editar_directorio(ConsultaFalsa(filas), sentencia, entorno, nombre, ruta)

    assert entorno.permisos == [] and sentencia.sqls == []


def test_editar_directorio_del_sistema_dice_que_no_se_puede_editar():
    with pytest.raises(DirectorioInvalido) as error:
        editar_directorio(
            ConsultaFalsa([("DATA_PUMP_DIR", "/x")]), SentenciaFalsa(), EntornoFalso(), "DATA_PUMP_DIR", "/r"
        )

    assert "no se puede editar ni eliminar" in str(error.value)


def test_editar_directorio_si_fallan_los_permisos_no_ejecuta_sentencias():
    entorno = EntornoFalso(fallo_permisos="chown: no such file")
    sentencia = SentenciaFalsa()

    with pytest.raises(OperacionEntornoFallida):
        editar_directorio(ConsultaFalsa([("R", "/x")]), sentencia, entorno, "r", "/opt/r")

    assert sentencia.sqls == []


def test_eliminar_directorio_ejecuta_solo_drop_directory():
    sentencia = SentenciaFalsa()

    eliminar_directorio(ConsultaFalsa([("RESPALDO", "/x")]), sentencia, "respaldo")

    assert sentencia.sqls == ["DROP DIRECTORY RESPALDO"]


@pytest.mark.parametrize(
    "nombre, filas, excepcion, texto",
    [
        ("1mal", [("R", "/x")], DirectorioInvalido, ""),
        ("otro", [("R", "/x")], DirectorioNoEncontrado, "otro".upper()),
        ("data_pump_dir", [("DATA_PUMP_DIR", "/x")], DirectorioInvalido, "no se puede editar ni eliminar"),
    ],
)
def test_eliminar_directorio_con_error_no_ejecuta_sentencias(nombre, filas, excepcion, texto):
    sentencia = SentenciaFalsa()

    with pytest.raises(excepcion) as error:
        eliminar_directorio(ConsultaFalsa(filas), sentencia, nombre)

    assert texto in str(error.value) and sentencia.sqls == []
