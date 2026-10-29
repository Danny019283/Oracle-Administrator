import pytest

from src.services import tablespaces
from src.services.identificadores import IdentificadorInvalido

MB = 1024 * 1024
CARPETA = "/opt/oracle/oradata/XE/XEPDB1/"


class ConsultaFalsa:
    def __init__(self):
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        if "dba_tablespaces" in sql:
            return [
                ("SYSTEM", "PERMANENT", "ONLINE", "NO", 300 * MB, 32768 * MB, 10 * MB, 1),
                ("TEMP", "TEMPORARY", "ONLINE", "NO", 20 * MB, 32768 * MB, 18 * MB, 1),
                ("USERS", "PERMANENT", "ONLINE", "NO", 100 * MB, 200 * MB, 25 * MB, 1),
                ("VACIO", "PERMANENT", "OFFLINE", "NO", 0, 0, 0, 0),
            ]
        if "INSTR(file_name" in sql:
            return [(CARPETA,)]
        if "dba_data_files" in sql:
            if params == {"tablespace": "TEMP"}:
                return [(1, CARPETA + "temp01.dbf", 20 * MB, "YES", 32768 * MB, "ONLINE")]
            return [(7, CARPETA + "users01.dbf", 100 * MB, "NO", 0, "AVAILABLE")]
        return []


class SentenciaFalsa:
    def __init__(self):
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)


def test_lista_tablespaces_con_uso_en_mb_y_porcentaje():
    lista = tablespaces.listar_tablespaces(ConsultaFalsa())

    users = next(t for t in lista if t["nombre"] == "USERS")
    assert users == {
        "nombre": "USERS",
        "tipo": "PERMANENT",
        "estado": "ONLINE",
        "bigfile": False,
        "tamano_mb": 100.0,
        "usado_mb": 75.0,
        "libre_mb": 25.0,
        "maximo_mb": 200.0,
        "porcentaje_uso": 75.0,
        "archivos": 1,
    }


def test_tablespace_sin_archivos_no_divide_entre_cero():
    lista = tablespaces.listar_tablespaces(ConsultaFalsa())

    vacio = next(t for t in lista if t["nombre"] == "VACIO")
    assert vacio["porcentaje_uso"] == 0


def test_la_consulta_incluye_temporales():
    consulta = ConsultaFalsa()

    tablespaces.listar_tablespaces(consulta)

    assert "dba_temp_files" in consulta.llamadas[0][0]
    assert "dba_temp_free_space" in consulta.llamadas[0][0]


def test_detalle_incluye_sus_datafiles():
    detalle = tablespaces.detalle_tablespace(ConsultaFalsa(), "users")

    assert detalle["nombre"] == "USERS"
    assert detalle["datafiles"] == [
        {
            "id": 7,
            "archivo": CARPETA + "users01.dbf",
            "tamano_mb": 100.0,
            "autoextensible": False,
            "maximo_mb": 0.0,
            "estado": "AVAILABLE",
        }
    ]


def test_detalle_de_tablespace_inexistente():
    with pytest.raises(tablespaces.TablespaceNoEncontrado):
        tablespaces.detalle_tablespace(ConsultaFalsa(), "NOEXISTE")


def test_nombre_de_tablespace_invalido():
    with pytest.raises(IdentificadorInvalido):
        tablespaces.detalle_tablespace(ConsultaFalsa(), "users; drop")


def test_crea_tablespace_permanente_en_la_carpeta_de_datafiles():
    sentencia = SentenciaFalsa()

    nombre = tablespaces.crear_tablespace(
        ConsultaFalsa(), sentencia, "ventas", "permanent", "Ventas01.dbf", "100m",
        autoextend=True, siguiente="10M", maximo="1G",
    )

    assert nombre == "VENTAS"
    assert sentencia.sqls == [
        f"CREATE TABLESPACE VENTAS DATAFILE '{CARPETA}ventas01.dbf' SIZE 100M "
        "AUTOEXTEND ON NEXT 10M MAXSIZE 1G"
    ]


def test_crea_tablespace_en_carpeta_estilo_windows():
    carpeta = "C:\\APP\\ORADATA\\XE\\"

    def consulta(sql, params=None):
        # Oracle solo devuelve la carpeta si la consulta corta también en «\»
        return [(carpeta if r"INSTR(file_name,'\',-1)" in sql else "",)]

    sentencia = SentenciaFalsa()

    tablespaces.crear_tablespace(consulta, sentencia, "ventas", "PERMANENT", "ventas01.dbf", "100M")

    assert sentencia.sqls[0].startswith(
        "CREATE TABLESPACE VENTAS DATAFILE 'C:\\APP\\ORADATA\\XE\\ventas01.dbf' SIZE 100M"
    )


def test_crea_tablespace_temporal_con_tempfile_y_sin_autoextend():
    sentencia = SentenciaFalsa()

    tablespaces.crear_tablespace(
        ConsultaFalsa(), sentencia, "temp2", "TEMPORARY", "temp02.dbf", "50M", autoextend=False
    )

    assert sentencia.sqls == [
        f"CREATE TEMPORARY TABLESPACE TEMP2 TEMPFILE '{CARPETA}temp02.dbf' SIZE 50M AUTOEXTEND OFF"
    ]


def test_crear_reune_todos_los_errores_y_no_ejecuta_nada():
    sentencia = SentenciaFalsa()

    with pytest.raises(tablespaces.TablespaceInvalido) as error:
        tablespaces.crear_tablespace(
            ConsultaFalsa(), sentencia, "", "UNDO", "../etc/passwd", "mucho",
            autoextend=True, siguiente="", maximo="infinito",
        )

    assert len(error.value.errores) == 6
    assert sentencia.sqls == []


@pytest.mark.parametrize("archivo", ["datos.txt", "/tmp/x.dbf", "a'b.dbf", "1datos.dbf"])
def test_rechaza_nombres_de_archivo_con_ruta_o_caracteres_raros(archivo):
    with pytest.raises(tablespaces.TablespaceInvalido):
        tablespaces.crear_tablespace(ConsultaFalsa(), SentenciaFalsa(), "X", "PERMANENT", archivo, "10M")


def test_agrega_datafile_a_tablespace_permanente():
    sentencia = SentenciaFalsa()

    tablespaces.agregar_archivo(ConsultaFalsa(), sentencia, "users", "users02.dbf", "50M", autoextend=False)

    assert sentencia.sqls == [
        f"ALTER TABLESPACE USERS ADD DATAFILE '{CARPETA}users02.dbf' SIZE 50M AUTOEXTEND OFF"
    ]


def test_agrega_tempfile_a_tablespace_temporal():
    sentencia = SentenciaFalsa()

    tablespaces.agregar_archivo(ConsultaFalsa(), sentencia, "TEMP", "temp02.dbf", "50M", autoextend=False)

    assert sentencia.sqls[0].startswith("ALTER TABLESPACE TEMP ADD TEMPFILE")


def test_redimensiona_un_datafile_del_tablespace():
    sentencia = SentenciaFalsa()

    tablespaces.redimensionar_archivo(ConsultaFalsa(), sentencia, "USERS", 7, "200m")

    assert sentencia.sqls == ["ALTER DATABASE DATAFILE 7 RESIZE 200M"]


def test_redimensiona_un_tempfile():
    sentencia = SentenciaFalsa()

    tablespaces.redimensionar_archivo(ConsultaFalsa(), sentencia, "TEMP", 1, "40M")

    assert sentencia.sqls == ["ALTER DATABASE TEMPFILE 1 RESIZE 40M"]


def test_no_redimensiona_archivos_de_otro_tablespace():
    sentencia = SentenciaFalsa()

    with pytest.raises(tablespaces.TablespaceInvalido):
        tablespaces.redimensionar_archivo(ConsultaFalsa(), sentencia, "USERS", 99, "200M")
    assert sentencia.sqls == []


def test_activa_y_desactiva_autoextend():
    sentencia = SentenciaFalsa()

    tablespaces.cambiar_autoextend(ConsultaFalsa(), sentencia, "USERS", 7, True, "5M", "unlimited")
    tablespaces.cambiar_autoextend(ConsultaFalsa(), sentencia, "USERS", 7, False)

    assert sentencia.sqls == [
        "ALTER DATABASE DATAFILE 7 AUTOEXTEND ON NEXT 5M MAXSIZE UNLIMITED",
        "ALTER DATABASE DATAFILE 7 AUTOEXTEND OFF",
    ]


@pytest.mark.parametrize(
    ("estado", "sql"),
    [
        ("offline", "ALTER TABLESPACE USERS OFFLINE NORMAL"),
        ("ONLINE", "ALTER TABLESPACE USERS ONLINE"),
        ("read  only", "ALTER TABLESPACE USERS READ ONLY"),
        ("READ WRITE", "ALTER TABLESPACE USERS READ WRITE"),
    ],
)
def test_cambia_el_estado(estado, sql):
    sentencia = SentenciaFalsa()

    tablespaces.cambiar_estado(ConsultaFalsa(), sentencia, "USERS", estado)

    assert sentencia.sqls == [sql]


@pytest.mark.parametrize("nombre", ["SYSTEM", "TEMP"])
def test_no_cambia_el_estado_de_system_ni_de_temporales(nombre):
    sentencia = SentenciaFalsa()

    with pytest.raises(tablespaces.TablespaceInvalido):
        tablespaces.cambiar_estado(ConsultaFalsa(), sentencia, nombre, "OFFLINE")
    assert sentencia.sqls == []


def test_estado_desconocido():
    with pytest.raises(tablespaces.TablespaceInvalido):
        tablespaces.cambiar_estado(ConsultaFalsa(), SentenciaFalsa(), "USERS", "DROP")
