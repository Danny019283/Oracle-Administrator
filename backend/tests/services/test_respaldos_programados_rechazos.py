from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services import respaldos_programados as rp
from src.services.directorios import Directorio
from src.services.politica_respaldo import Programacion
from src.services.respaldo import SolicitudInvalida
from src.services.respaldo_full import SinArchivelog
from tests.services.entorno_falso import EntornoFalso


class EntornoWindows(EntornoFalso):
    tipo_ruta = PureWindowsPath


class Programador:
    def __init__(self):
        self.instalaciones = []

    def instalar(self, id_programacion, prog, ruta_script):
        self.instalaciones.append(id_programacion)


class Sentencia:
    def __init__(self):
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append(sql)


class Consulta:
    def __init__(self, modo="ARCHIVELOG", existentes=(), sin_tabla=False):
        self.modo = modo
        self.existentes = existentes
        self.sin_tabla = sin_tabla
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)
        if "log_mode" in sql:
            return [(self.modo,)]
        if "SELECT ID FROM" in sql:  # lectura del ID tras el INSERT
            return [(7,)]
        if self.sin_tabla:
            raise _TablaInexistente("ORA-00942: table or view does not exist")
        return [_fila(n) for n in self.existentes]


class _TablaInexistente(rp.oracledb.Error):
    pass


def _fila(nombre):
    from datetime import datetime

    return (1, nombre, "FULL", "DIARIO", "01:00", None, None, "D", "/r/s.sh", "/r/s.rman",
            "local", "OracleAdmin_1", datetime(2026, 1, 1), None, None)


def _prog(**kw):
    datos = dict(nombre="diario", directorio="D", politica="FULL", frecuencia="DIARIO", hora="02:30")
    datos.update(kw)
    return Programacion(**datos)


def _intentar(prog=None, directorios=None, consulta=None, entorno=None):
    entorno = entorno or EntornoFalso()
    consulta = consulta or Consulta()
    sentencia, programador = Sentencia(), Programador()
    directorios = directorios if directorios is not None else [Directorio("D", "/resp")]
    with pytest.raises(Exception) as info:
        rp.crear(consulta, sentencia, directorios, prog or _prog(), entorno, programador, "S", "local")
    # un rechazo no deja nada hecho
    assert sentencia.llamadas == []
    assert programador.instalaciones == []
    assert entorno.escrituras == [] and entorno.herramientas == [] and entorno.ejecuciones == []
    assert entorno.consultas_entorno == []
    return info.value, consulta


@pytest.mark.parametrize(
    "prog, texto",
    [
        (_prog(nombre="mi respaldo"), "nombre"),
        (_prog(nombre="a;b"), "nombre"),
        (_prog(nombre="../x"), "nombre"),
        (_prog(directorio="NOEXISTE"), "directorio"),
        (_prog(hora="24:00"), "hora"),
        (_prog(frecuencia="SEMANAL", dia=7), "día"),
        (_prog(frecuencia="HORAS", intervalo_horas=4, politica="FULL"), "TRANSACCIONAL"),
    ],
)
def test_datos_invalidos_son_solicitud_invalida_sin_efectos(prog, texto):
    error, consulta = _intentar(prog)
    assert isinstance(error, SolicitudInvalida)
    assert error.errores and any(texto in e for e in error.errores)
    assert consulta.sqls == []  # ni ARCHIVELOG ni listado


@pytest.mark.parametrize("ruta", ["/mi respaldo", "/r$HOME", "/r'x", '/r"x', "/r`x`", "/a;b", "/a&b", "/a|b",
                                  "/a<b", "/a>b", "/a(b", "/a)b", "/a*b", "/a?b", "/a!b", "/a%b", "/a\nb", "/a\rb"])
def test_ruta_con_caracteres_no_admitidos_en_posix_se_rechaza(ruta):
    error, consulta = _intentar(directorios=[Directorio("D", ruta)])
    assert isinstance(error, SolicitudInvalida)
    assert error.errores[0].startswith(
        "La ruta del directorio contiene caracteres no admitidos para un respaldo programado:"
    )
    assert consulta.sqls == []


def test_ruta_con_espacio_se_admite_en_windows():
    entorno = EntornoWindows(variables_entorno={"ORACLE_HOME": "C:\\h"})
    sentencia = Sentencia()
    creada = rp.crear(
        Consulta(), sentencia, [Directorio("D", "C:\\mis respaldos")], _prog(), entorno, Programador(), "S", "local"
    )
    assert creada.ruta_script.startswith("C:\\mis respaldos\\scripts_programados")


def test_ruta_con_dolar_se_rechaza_tambien_en_windows():
    entorno = EntornoWindows()
    error, _ = _intentar(directorios=[Directorio("D", "C:\\r$x")], entorno=entorno)
    assert isinstance(error, SolicitudInvalida)


def test_validar_ruta_directorio():
    assert rp.errores_ruta_directorio("/ok/ruta-1_a.b", PurePosixPath) == []
    assert rp.errores_ruta_directorio("C:\\a b\\c", PureWindowsPath) == []
    errores = rp.errores_ruta_directorio("/a b$", PurePosixPath)
    assert len(errores) == 1 and "$" in errores[0]


def test_noarchivelog_lanza_sin_archivelog_sin_efectos():
    error, consulta = _intentar(consulta=Consulta(modo="NOARCHIVELOG"))
    assert isinstance(error, SinArchivelog)
    assert "ARCHIVELOG" in str(error)
    assert len(consulta.sqls) == 1  # solo se consultó ARCHIVELOG, no el listado


def test_nombre_repetido_con_otra_capitalizacion_es_conflicto():
    error, _ = _intentar(prog=_prog(nombre="Diario"), consulta=Consulta(existentes=["diario"]))
    assert isinstance(error, rp.ProgramacionDuplicada)
    assert str(error) == "Ya existe una programación con ese nombre"


def test_tabla_inexistente_no_es_falso_conflicto():
    entorno = EntornoFalso(variables_entorno={"ORACLE_HOME": "/h"})
    sentencia, programador = Sentencia(), Programador()
    creada = rp.crear(
        Consulta(sin_tabla=True), sentencia, [Directorio("D", "/resp")], _prog(), entorno, programador, "S", "local"
    )
    assert creada.ruta_script == "/resp/scripts_programados/diario.sh"


def test_otro_nombre_existente_no_bloquea():
    entorno = EntornoFalso(variables_entorno={"ORACLE_HOME": "/h"})
    rp.crear(
        Consulta(existentes=["otro"]), Sentencia(), [Directorio("D", "/resp")], _prog(), entorno, Programador(),
        "S", "local",
    )
    assert entorno.escrituras


def test_orden_datos_invalidos_ganan_a_ruta_archivelog_y_duplicado():
    consulta = Consulta(modo="NOARCHIVELOG", existentes=["diario"])
    error, consulta = _intentar(
        prog=_prog(hora="24:00"), directorios=[Directorio("D", "/mala ruta")], consulta=consulta
    )
    assert isinstance(error, SolicitudInvalida) and any("hora" in e for e in error.errores)
    assert consulta.sqls == []


def test_orden_ruta_gana_a_archivelog():
    consulta = Consulta(modo="NOARCHIVELOG")
    error, consulta = _intentar(directorios=[Directorio("D", "/mala ruta")], consulta=consulta)
    assert isinstance(error, SolicitudInvalida)
    assert consulta.sqls == []


def test_orden_archivelog_gana_a_nombre_repetido():
    consulta = Consulta(modo="NOARCHIVELOG", existentes=["diario"])
    error, consulta = _intentar(consulta=consulta)
    assert isinstance(error, SinArchivelog)
    assert len(consulta.sqls) == 1
