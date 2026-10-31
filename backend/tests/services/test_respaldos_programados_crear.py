import dataclasses
from pathlib import PureWindowsPath

import pytest

from src.services import respaldos_programados as rp
from src.services.directorios import Directorio
from src.services.politica_respaldo import Programacion, envoltorio, script_rman
from tests.services.entorno_falso import EntornoFalso

HOME = "/opt/oracle/product/21c/dbhome_1"


class Registro:
    """Un único registro de eventos para comprobar el orden de las operaciones."""

    def __init__(self):
        self.eventos = []


class EntornoRegistrado(EntornoFalso):
    def __init__(self, registro, **kwargs):
        super().__init__(**kwargs)
        self.registro = registro

    def ejecutar(self, comando):
        self.registro.eventos.append("politica")
        return super().ejecutar(comando)

    def escribir_archivo(self, ruta, texto, ejecutable):
        super().escribir_archivo(ruta, texto, ejecutable)
        self.registro.eventos.append(("escribir", str(ruta)))


class EntornoWindows(EntornoRegistrado):
    tipo_ruta = PureWindowsPath


class ProgramadorFalso:
    def __init__(self, registro):
        self.registro = registro
        self.instalaciones = []

    def instalar(self, id_programacion, prog, ruta_script):
        self.registro.eventos.append("instalar")
        self.instalaciones.append((id_programacion, prog, ruta_script))


class Sentencia:
    def __init__(self, registro):
        self.registro = registro
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.registro.eventos.append({"CREATE": "tabla", "INSERT": "insert", "UPDATE": "tarea"}[sql.split()[0]])
        self.llamadas.append((sql, params))


class Consulta:
    def __init__(self, registro):
        self.registro = registro

    def __call__(self, sql, params=None):
        if "log_mode" in sql:
            self.registro.eventos.append("archivelog")
            return [("ARCHIVELOG",)]
        if "ORDER BY ID" in sql:
            return []  # listado previo (nombre repetido): aún no hay programaciones
        return [(7,)]


def montar(entorno_cls=EntornoRegistrado, home=HOME):
    registro = Registro()
    entorno = entorno_cls(registro, variables_entorno={"ORACLE_HOME": home})
    return registro, entorno, Consulta(registro), Sentencia(registro), ProgramadorFalso(registro)


def test_crear_camino_feliz_posix_diario_full():
    registro, entorno, consulta, sentencia, programador = montar()
    prog = Programacion("diario", "DIR_RESP", "FULL", "DIARIO", hora="02:30")
    directorios = [Directorio("OTRO", "/otra"), Directorio("DIR_RESP", "/resp")]

    creada = rp.crear(consulta, sentencia, directorios, prog, entorno, programador, "ORCLCDB", "contenedor")

    rman, sh = "/resp/scripts_programados/diario.rman", "/resp/scripts_programados/diario.sh"
    assert registro.eventos == [
        "archivelog", "tabla", "politica", ("escribir", rman), ("escribir", sh), "insert", "tarea", "instalar",
    ]
    assert entorno.escrituras == [
        (entorno.tipo_ruta(rman), script_rman("FULL", entorno.tipo_ruta("/resp")), False),
        (
            entorno.tipo_ruta(sh),
            envoltorio("diario", "ORCLCDB", HOME, entorno.tipo_ruta(rman), entorno.tipo_ruta("/resp")),
            True,
        ),
    ]
    assert "ORACLE_HOME" in entorno.consultas_entorno
    sql, params = sentencia.llamadas[1]
    assert sql.startswith("INSERT INTO SYSTEM.RESPALDOS_PROGRAMADOS")
    assert params == {
        "nombre": "diario", "politica": "FULL", "frecuencia": "DIARIO", "hora": "02:30",
        "dia": None, "intervalo_horas": None, "directorio": "DIR_RESP", "ruta_script": sh,
        "ruta_rman": rman, "entorno": "contenedor", "tarea": "OracleAdmin_diario",
    }
    # el ID solo existe tras el INSERT: la tarea definitiva (RN-13) se fija justo después
    sql, params = sentencia.llamadas[2]
    assert sql.startswith("UPDATE SYSTEM.RESPALDOS_PROGRAMADOS SET TAREA")
    assert params == {"id": 7, "tarea": "OracleAdmin_7"}
    assert programador.instalaciones == [(7, prog, sh)]
    assert creada == rp.ProgramacionCreada(id=7, ruta_script=sh, ruta_rman=rman)
    with pytest.raises(dataclasses.FrozenInstanceError):
        creada.id = 8


def test_crear_ruta_del_directory_viene_de_all_directories_no_del_cliente():
    registro, entorno, consulta, sentencia, programador = montar()
    prog = Programacion("x", "DIR_RESP", "FULL", "DIARIO", hora="01:00")
    rp.crear(consulta, sentencia, [Directorio("DIR_RESP", "/oficial")], prog, entorno, programador, "S", "local")
    assert all(str(r).startswith("/oficial/scripts_programados/") for r, _, _ in entorno.escrituras)


def test_crear_windows_transaccional_por_horas():
    registro, entorno, consulta, sentencia, programador = montar(EntornoWindows, home="C:\\oracle\\home")
    prog = Programacion("tx", "DIR_W", "TRANSACCIONAL", "HORAS", intervalo_horas=4)

    creada = rp.crear(consulta, sentencia, [Directorio("DIR_W", "C:\\resp")], prog, entorno, programador, "ORCL", "local")

    rman, bat = "C:\\resp\\scripts_programados\\tx.rman", "C:\\resp\\scripts_programados\\tx.bat"
    assert creada == rp.ProgramacionCreada(id=7, ruta_script=bat, ruta_rman=rman)
    assert [(str(r), e) for r, _, e in entorno.escrituras] == [(rman, False), (bat, True)]
    assert entorno.escrituras[0][1] == script_rman("TRANSACCIONAL", PureWindowsPath("C:\\resp"))
    assert entorno.escrituras[1][1] == envoltorio(
        "tx", "ORCL", "C:\\oracle\\home", PureWindowsPath(rman), PureWindowsPath("C:\\resp")
    )
    params = sentencia.llamadas[1][1]
    assert params["frecuencia"] == "HORAS" and params["intervalo_horas"] == 4
    assert params["hora"] is None and params["dia"] is None
    assert params["ruta_script"] == bat
    assert sentencia.llamadas[2][1] == {"id": 7, "tarea": "OracleAdmin_7"}
    assert programador.instalaciones == [(7, prog, bat)]


@pytest.mark.parametrize(
    "prog, hora, dia",
    [
        (Programacion("s", "D", "INCREMENTAL", "SEMANAL", hora="03:00"), "03:00", 0),
        (Programacion("s", "D", "INCREMENTAL", "SEMANAL", hora="03:00", dia=5), "03:00", 5),
        (Programacion("s", "D", "FULL", "MENSUAL", hora="04:15"), "04:15", 1),
        (Programacion("s", "D", "FULL", "MENSUAL", hora="04:15", dia=28), "04:15", 28),
    ],
)
def test_crear_guarda_el_dia_efectivo_de_la_frecuencia(prog, hora, dia):
    registro, entorno, consulta, sentencia, programador = montar()
    rp.crear(consulta, sentencia, [Directorio("D", "/r")], prog, entorno, programador, "S", "local")
    params = sentencia.llamadas[1][1]
    assert (params["hora"], params["dia"], params["intervalo_horas"]) == (hora, dia, None)
