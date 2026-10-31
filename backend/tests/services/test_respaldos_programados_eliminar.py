from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services import respaldos_programados as rp
from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida
from tests.services.entorno_falso import EntornoFalso

CARPETA = "/resp/scripts_programados"
SH = f"{CARPETA}/diario.sh"
RMAN = f"{CARPETA}/diario.rman"
BAT = r"C:\resp\scripts_programados\diario.bat"
RMAN_WIN = r"C:\resp\scripts_programados\diario.rman"


class EntornoRegistrado(EntornoFalso):
    def __init__(self, eventos, **kwargs):
        super().__init__(**kwargs)
        self.eventos = eventos

    def borrar_archivo(self, ruta):
        self.eventos.append(("borrar", str(ruta)))
        super().borrar_archivo(ruta)


class EntornoWindows(EntornoRegistrado):
    tipo_ruta = PureWindowsPath


class Programador:
    def __init__(self, eventos, error=None):
        self.eventos = eventos
        self.error = error

    def eliminar(self, id_programacion):
        self.eventos.append(("programador", id_programacion))
        if self.error:
            raise self.error


class Base:
    """Doble de consulta + sentencia: la fila existe hasta que se ejecuta el DELETE."""

    def __init__(self, eventos, ruta_script=SH, ruta_rman=RMAN, existe=True):
        self.eventos = eventos
        self.existe = existe
        self.fila = (7, "diario", "FULL", "DIARIO", "02:30", None, None, "DIR_RESP", ruta_script,
                     ruta_rman, "local", "OracleAdmin_7", None, None, None)
        self.consultas = []
        self.sentencias = []

    def consulta(self, sql, params=None):
        self.consultas.append((sql, params))
        return [self.fila] if self.existe else []

    def sentencia(self, sql, params=None):
        self.sentencias.append((sql, params))
        self.eventos.append(("fila", sql, params))
        self.existe = False


def preparar(error_programador=None, clase_entorno=EntornoRegistrado, **base):
    eventos = []
    return (eventos, Base(eventos, **base), clase_entorno(eventos), Programador(eventos, error_programador))


def test_eliminar_quita_tarea_borra_los_dos_archivos_y_la_fila_en_orden():
    eventos, base, entorno, programador = preparar()

    nombre = rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    assert nombre == "diario"
    assert eventos == [
        ("programador", 7),
        ("borrar", SH),
        ("borrar", RMAN),
        ("fila", "DELETE FROM SYSTEM.RESPALDOS_PROGRAMADOS WHERE ID = :id", {"id": 7}),
    ]
    assert entorno.borrados == [PurePosixPath(SH), PurePosixPath(RMAN)]  # RN-12: solo esos dos


def test_eliminar_inexistente_no_toca_nada():
    eventos, base, entorno, programador = preparar(existe=False)

    with pytest.raises(rp.ProgramacionNoEncontrada):
        rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    assert eventos == [] and entorno.borrados == []
    assert base.consultas[0][1] == {"id": 7}


@pytest.mark.parametrize("error", [OperacionEntornoFallida("crontab falló"), HerramientaNoDisponible("crontab")])
def test_eliminar_falla_el_programador_propaga_y_no_borra_nada(error):
    eventos, base, entorno, programador = preparar(error_programador=error)

    with pytest.raises(type(error)) as info:
        rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    assert info.value is error
    assert eventos == [("programador", 7)]
    assert entorno.borrados == [] and base.sentencias == []


def test_eliminar_falla_el_borrado_del_envoltorio_conserva_la_fila():
    eventos, base, entorno, programador = preparar()
    entorno.fallo_borrado = "permiso denegado"

    with pytest.raises(OperacionEntornoFallida, match="permiso denegado"):
        rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    assert eventos == [("programador", 7), ("borrar", SH)]
    assert base.sentencias == [] and base.existe


def test_eliminar_falla_el_borrado_del_rman_conserva_la_fila():
    eventos, base, entorno, programador = preparar()

    def borrar(ruta):
        eventos.append(("borrar", str(ruta)))
        if str(ruta) == RMAN:
            raise OperacionEntornoFallida("permiso denegado")

    entorno.borrar_archivo = borrar

    with pytest.raises(OperacionEntornoFallida):
        rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    assert eventos == [("programador", 7), ("borrar", SH), ("borrar", RMAN)]
    assert base.sentencias == []


def test_eliminar_reintento_tras_fallo_de_borrado_termina():
    eventos, base, entorno, programador = preparar()
    entorno.fallo_borrado = "permiso denegado"
    with pytest.raises(OperacionEntornoFallida):
        rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    entorno.fallo_borrado = None
    assert rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7) == "diario"
    assert len(base.sentencias) == 1 and not base.existe


def test_eliminar_variante_windows():
    eventos, base, entorno, programador = preparar(clase_entorno=EntornoWindows, ruta_script=BAT, ruta_rman=RMAN_WIN)

    assert rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7) == "diario"

    assert entorno.borrados == [PureWindowsPath(BAT), PureWindowsPath(RMAN_WIN)]
    assert eventos[0] == ("programador", 7) and eventos[-1][0] == "fila"


def test_eliminar_dos_veces_la_segunda_es_no_encontrada():
    eventos, base, entorno, programador = preparar()
    rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)
    previos = len(eventos)

    with pytest.raises(rp.ProgramacionNoEncontrada):
        rp.eliminar(base.consulta, base.sentencia, entorno, programador, 7)

    assert len(eventos) == previos
