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
    """Ejecutor falso: `schtasks` con creación, borrado y consulta configurables."""

    def __init__(self, creacion=None, borrado=None, consulta=None, ausente=False):
        self.creacion = creacion or Salida(0, "")
        self.borrado = borrado or Salida(0, "")
        self.consulta = consulta or Salida(0, "")
        self.ausente = ausente
        self.llamadas = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append(list(args))
        if self.ausente:
            raise HerramientaNoDisponible(args[0])
        return {"/Create": self.creacion, "/Delete": self.borrado}.get(args[1], self.consulta)


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


BORRAR = ["schtasks", "/Delete", "/TN", "OracleAdmin_7", "/F"]
CONSULTAR = ["schtasks", "/Query", "/TN", "OracleAdmin_7"]
FALLO = Salida(1, "ERROR: fallo al borrar")


def test_eliminar_con_exito_borra_sin_consultar():
    falso = SchtasksFalso()
    ProgramadorSchtasks(falso).eliminar(7)
    assert falso.llamadas == [BORRAR]


def test_eliminar_fallido_con_la_tarea_existente_lanza_con_la_salida_del_delete():
    falso = SchtasksFalso(borrado=FALLO, consulta=Salida(0, ""))
    with pytest.raises(OperacionEntornoFallida, match="fallo al borrar"):
        ProgramadorSchtasks(falso).eliminar(7)
    assert falso.llamadas == [BORRAR, CONSULTAR]


@pytest.mark.parametrize("texto", ["ERROR: Acceso denegado.", "ERROR: Access is denied."])
def test_eliminar_fallido_y_consulta_denegada_lanza_por_permisos(texto):
    falso = SchtasksFalso(borrado=FALLO, consulta=Salida(1, texto))
    with pytest.raises(OperacionEntornoFallida, match="fallo al borrar"):
        ProgramadorSchtasks(falso).eliminar(7)


def test_eliminar_con_denegado_solo_en_la_salida_del_delete_lanza():
    falso = SchtasksFalso(borrado=Salida(1, "ERROR: Access is denied."), consulta=Salida(1, "ERROR: x"))
    with pytest.raises(OperacionEntornoFallida, match="denied"):
        ProgramadorSchtasks(falso).eliminar(7)


def test_eliminar_fallido_y_consulta_sin_marcas_es_tarea_inexistente_y_no_falla():
    falso = SchtasksFalso(borrado=FALLO, consulta=Salida(1, "ERROR: no se puede encontrar la tarea"))
    ProgramadorSchtasks(falso).eliminar(7)
    assert falso.llamadas == [BORRAR, CONSULTAR]


@pytest.mark.parametrize("operacion", ["instalar", "eliminar"])
def test_schtasks_ausente_se_propaga(operacion):
    programador = ProgramadorSchtasks(SchtasksFalso(ausente=True))
    with pytest.raises(HerramientaNoDisponible):
        programador.instalar(7, DIARIO, RUTA) if operacion == "instalar" else programador.eliminar(7)
