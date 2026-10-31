from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services import respaldos_programados as rp
from src.services.directorios import Directorio
from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida
from src.services.politica_respaldo import Programacion
from src.services.respaldo import RespaldoFallido
from tests.services.entorno_falso import EntornoFalso

RMAN = "/resp/scripts_programados/diario.rman"
SH = "/resp/scripts_programados/diario.sh"


class _ErrorOracle(rp.oracledb.Error):
    pass


class EntornoRegistrado(EntornoFalso):
    def __init__(self, eventos, escribir_falla_en=None, **kwargs):
        super().__init__(**kwargs)
        self.eventos = eventos
        self.escribir_falla_en = escribir_falla_en

    def escribir_archivo(self, ruta, texto, ejecutable):
        if self.escribir_falla_en and str(ruta).endswith(self.escribir_falla_en):
            raise OperacionEntornoFallida("sin espacio en disco")
        super().escribir_archivo(ruta, texto, ejecutable)
        self.eventos.append(("escribir", str(ruta)))

    def borrar_archivo(self, ruta):
        self.eventos.append(("borrar", str(ruta)))
        super().borrar_archivo(ruta)


class Programador:
    def __init__(self, eventos, error=None):
        self.eventos = eventos
        self.error = error
        self.instalaciones = []

    def instalar(self, id_programacion, prog, ruta_script):
        self.eventos.append("instalar")
        if self.error:
            raise self.error
        self.instalaciones.append(id_programacion)


class Sentencia:
    """Registra las sentencias; `fallos` asocia el inicio del SQL con la excepción a lanzar."""

    def __init__(self, eventos, fallos=None):
        self.eventos = eventos
        self.fallos = fallos or {}

    def __call__(self, sql, params=None):
        evento = {"CREATE": "tabla", "INSERT": "insert", "UPDATE": "tarea", "DELETE": "fila"}[sql.split()[0]]
        self.eventos.append((evento, params) if evento == "fila" else evento)
        if evento in self.fallos:
            raise self.fallos[evento]


def consulta(sql, params=None):
    if "log_mode" in sql:
        return [("ARCHIVELOG",)]
    if "ORDER BY ID" in sql:
        return []
    return [(7,)]


def intentar(*, entorno=None, fallos=None, error_programador=None, home="/opt/home", **kw):
    eventos = []
    entorno = entorno or EntornoRegistrado(eventos, variables_entorno={"ORACLE_HOME": home}, **kw)
    entorno.eventos = eventos
    sentencia, programador = Sentencia(eventos, fallos), Programador(eventos, error_programador)
    prog = Programacion("diario", "D", "FULL", "DIARIO", hora="02:30")
    with pytest.raises(Exception) as info:
        rp.crear(consulta, sentencia, [Directorio("D", "/resp")], prog, entorno, programador, "S", "local")
    return info.value, eventos, entorno, programador


def test_fa4a_falla_la_tabla_se_propaga_sin_escribir_ni_insertar():
    error = _ErrorOracle("ORA-01031: insufficient privileges")
    propagado, eventos, entorno, programador = intentar(fallos={"tabla": error})
    assert propagado is error
    assert eventos == ["tabla"]
    assert programador.instalaciones == []


def test_fa4a_falla_la_politica_global_se_propaga_sin_escribir_ni_insertar():
    propagado, eventos, entorno, programador = intentar(codigo=1, texto="RMAN-00571")
    assert isinstance(propagado, RespaldoFallido)
    assert eventos == ["tabla"]  # la tabla ya creada se queda
    assert entorno.escrituras == [] and entorno.borrados == []


@pytest.mark.parametrize("home", [None, "", "/ruta con;espacio"])
def test_oracle_home_ausente_o_invalido_no_escribe_nada(home):
    propagado, eventos, entorno, programador = intentar(home=home)
    assert isinstance(propagado, OperacionEntornoFallida)
    assert "No se pudo determinar ORACLE_HOME del servidor de Oracle" in str(propagado)
    assert eventos == ["tabla"]
    assert entorno.escrituras == [] and entorno.borrados == []


def test_fa5a_falla_la_escritura_del_rman_no_borra_nada_ni_inserta():
    propagado, eventos, entorno, programador = intentar(escribir_falla_en=".rman")
    assert isinstance(propagado, OperacionEntornoFallida) and str(propagado) == "sin espacio en disco"
    assert eventos == ["tabla"]
    assert entorno.borrados == []


def test_fa5a_falla_la_escritura_del_envoltorio_borra_el_rman():
    propagado, eventos, entorno, programador = intentar(escribir_falla_en=".sh")
    assert isinstance(propagado, OperacionEntornoFallida) and str(propagado) == "sin espacio en disco"
    assert eventos == ["tabla", ("escribir", RMAN), ("borrar", RMAN)]
    assert programador.instalaciones == []


def test_fa7a_falla_el_insert_borra_los_scripts_en_orden_inverso():
    error = _ErrorOracle("ORA-01653: unable to extend table")
    propagado, eventos, entorno, programador = intentar(fallos={"insert": error})
    assert propagado is error
    assert eventos == [
        "tabla", ("escribir", RMAN), ("escribir", SH), "insert", ("borrar", SH), ("borrar", RMAN),
    ]  # no hay fila que quitar: el INSERT no se completó


def test_fa7a_ora_00001_en_el_insert_es_programacion_duplicada():
    error = _ErrorOracle("ORA-00001: unique constraint (SYSTEM.SYS_C001) violated")
    propagado, eventos, entorno, programador = intentar(fallos={"insert": error})
    assert isinstance(propagado, rp.ProgramacionDuplicada)
    assert str(propagado) == "Ya existe una programación con ese nombre"
    assert eventos[-2:] == [("borrar", SH), ("borrar", RMAN)]
    assert programador.instalaciones == []


def test_fa7a_falla_el_update_de_tarea_quita_fila_y_scripts():
    error = _ErrorOracle("ORA-03113: end-of-file")
    propagado, eventos, entorno, programador = intentar(fallos={"tarea": error})
    assert propagado is error
    assert eventos == [
        "tabla", ("escribir", RMAN), ("escribir", SH), "insert", "tarea",
        ("fila", {"id": 7}), ("borrar", SH), ("borrar", RMAN),
    ]
    assert "instalar" not in eventos


def test_fa7a_ora_00001_en_el_update_tambien_es_duplicada():
    propagado, eventos, _, _ = intentar(fallos={"tarea": _ErrorOracle("ORA-00001: unique constraint")})
    assert isinstance(propagado, rp.ProgramacionDuplicada)
    assert eventos[-3:] == [("fila", {"id": 7}), ("borrar", SH), ("borrar", RMAN)]


@pytest.mark.parametrize(
    "error",
    [OperacionEntornoFallida("crontab: error"), HerramientaNoDisponible("crontab"), RuntimeError("inesperado")],
)
def test_fa6a_falla_el_programador_quita_fila_y_scripts(error):
    propagado, eventos, entorno, programador = intentar(error_programador=error)
    assert propagado is error
    assert eventos == [
        "tabla", ("escribir", RMAN), ("escribir", SH), "insert", "tarea", "instalar",
        ("fila", {"id": 7}), ("borrar", SH), ("borrar", RMAN),
    ]
    assert programador.instalaciones == []


def test_un_fallo_al_deshacer_no_tapa_el_error_original_y_sigue_con_el_resto():
    original = OperacionEntornoFallida("crontab: error")
    propagado, eventos, entorno, _ = intentar(
        error_programador=original,
        fallos={"fila": _ErrorOracle("ORA-03114: not connected")},
        fallo_borrado="permiso denegado",
    )
    assert propagado is original
    assert eventos[-3:] == [("fila", {"id": 7}), ("borrar", SH), ("borrar", RMAN)]


def test_un_fallo_al_deshacer_tras_error_de_escritura_no_tapa_el_original():
    propagado, eventos, _, _ = intentar(escribir_falla_en=".sh", fallo_borrado="permiso denegado")
    assert str(propagado) == "sin espacio en disco"
    assert eventos[-1] == ("borrar", RMAN)


def test_ruta_posix_rechaza_barra_invertida_y_blancos():
    for ruta in ["/a\\b", "/a\tb", "/a\u00a0b", "/a\x0bb"]:
        assert rp.errores_ruta_directorio(ruta, PurePosixPath), ruta


@pytest.mark.parametrize("tipo", [PurePosixPath, PureWindowsPath])
@pytest.mark.parametrize("caracter", ["[", "]", "{", "}", "\t", "\u00a0"])
def test_ruta_rechaza_corchetes_llaves_y_blancos_especiales_en_cualquier_entorno(tipo, caracter):
    assert rp.errores_ruta_directorio(f"/a{caracter}b", tipo)


def test_ruta_windows_admite_espacio_simple_y_barra_invertida():
    assert rp.errores_ruta_directorio("C:\\mis respaldos\\x", PureWindowsPath) == []
