import pytest

from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida, Salida
from src.services.politica_respaldo import Programacion
from src.services.programador_tareas import ProgramadorSchtasks, ProgramadorTareas, argumentos_schtasks

RUTA = r"C:\Program Files\backup\scripts_programados\p.bat"
PROGRAMACIONES = [
    Programacion("p", "BACKUP", "FULL", "DIARIO", "05:30"),
    Programacion("p", "BACKUP", "FULL", "SEMANAL", "02:00", 3),
    Programacion("p", "BACKUP", "FULL", "MENSUAL", "01:15", 10),
    Programacion("p", "BACKUP", "TRANSACCIONAL", "HORAS", None, None, 4),
]
DIARIO = PROGRAMACIONES[0]


class SchtasksFalso:
    """Ejecutor falso: `schtasks` con consulta, creación y borrado configurables."""

    def __init__(self, existe=True, creacion=None, borrado=None, ausente=False):
        self.existe = existe
        self.creacion = creacion or Salida(0, "")
        self.borrado = borrado or Salida(0, "")
        self.ausente = ausente
        self.llamadas = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append(list(args))
        if self.ausente:
            raise HerramientaNoDisponible(args[0])
        if args[1] == "/Query":
            return Salida(0 if self.existe else 1, "ERROR: no se puede encontrar la tarea")
        return self.creacion if args[1] == "/Create" else self.borrado


def test_es_un_programador_de_tareas():
    assert issubclass(ProgramadorSchtasks, ProgramadorTareas)


@pytest.mark.parametrize("prog", PROGRAMACIONES)
def test_instalar_ejecuta_schtasks_con_los_argumentos_exactos(prog):
    falso = SchtasksFalso()
    ProgramadorSchtasks(falso).instalar(7, prog, RUTA)
    esperado = ["schtasks", *argumentos_schtasks(prog, 7, RUTA)]
    assert falso.llamadas == [esperado]
    assert esperado[-1] == "/F" and esperado[1:4] == ["/Create", "/TN", "OracleAdmin_7"]
    assert f'"{RUTA}"' in esperado


def test_instalar_dos_veces_repite_la_misma_llamada_con_f():
    falso = SchtasksFalso()
    programador = ProgramadorSchtasks(falso)
    programador.instalar(7, DIARIO, RUTA)
    programador.instalar(7, DIARIO, RUTA)
    assert falso.llamadas[0] == falso.llamadas[1] and falso.llamadas[0][-1] == "/F"
    assert len(falso.llamadas) == 2


def test_instalar_con_error_lanza_con_la_salida():
    falso = SchtasksFalso(creacion=Salida(1, "ERROR: acceso denegado"))
    with pytest.raises(OperacionEntornoFallida, match="acceso denegado"):
        ProgramadorSchtasks(falso).instalar(7, DIARIO, RUTA)


def test_eliminar_inexistente_solo_consulta():
    falso = SchtasksFalso(existe=False)
    ProgramadorSchtasks(falso).eliminar(7)
    assert falso.llamadas == [["schtasks", "/Query", "/TN", "OracleAdmin_7"]]


def test_eliminar_existente_consulta_y_borra():
    falso = SchtasksFalso()
    ProgramadorSchtasks(falso).eliminar(7)
    assert falso.llamadas == [
        ["schtasks", "/Query", "/TN", "OracleAdmin_7"],
        ["schtasks", "/Delete", "/TN", "OracleAdmin_7", "/F"],
    ]


def test_eliminar_con_error_lanza_con_la_salida():
    falso = SchtasksFalso(borrado=Salida(1, "ERROR: acceso denegado al borrar"))
    with pytest.raises(OperacionEntornoFallida, match="acceso denegado al borrar"):
        ProgramadorSchtasks(falso).eliminar(7)


@pytest.mark.parametrize("operacion", ["instalar", "eliminar"])
def test_schtasks_ausente_se_propaga(operacion):
    programador = ProgramadorSchtasks(SchtasksFalso(ausente=True))
    with pytest.raises(HerramientaNoDisponible):
        programador.instalar(7, DIARIO, RUTA) if operacion == "instalar" else programador.eliminar(7)
