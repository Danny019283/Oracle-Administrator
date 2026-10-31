import pytest

from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida, Salida
from src.services.politica_respaldo import Programacion
from src.services.programador_tareas import ProgramadorCron, ProgramadorTareas

DIARIO = Programacion("p", "BACKUP", "FULL", "DIARIO", "05:30")
SEMANAL = Programacion("p", "BACKUP", "FULL", "SEMANAL", "02:00", 3)
AJENA = "0 1 * * * /usr/bin/otra-cosa"
RUTA = "/u01/backup/scripts_programados/p.sh"


class CrontabFalso:
    def __init__(self, texto=None, lectura=None, escritura=None, ausente=False):
        self.texto = texto  # None = sin crontab
        self.lectura = lectura  # Salida forzada para -l
        self.escritura = escritura  # Salida forzada para -
        self.ausente = ausente
        self.llamadas = []
        self.escrituras = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append((list(args), entrada, variables))
        if self.ausente:
            raise HerramientaNoDisponible(args[0])
        if args[-1] == "-l":
            if self.lectura:
                return self.lectura
            if self.texto is None:
                return Salida(1, "no crontab for user")
            return Salida(0, self.texto.rstrip("\n"))
        if self.escritura:
            return self.escritura
        self.texto = entrada
        self.escrituras.append(entrada)
        return Salida(0, "")


def test_es_un_puerto_programador():
    assert issubclass(ProgramadorCron, ProgramadorTareas)


@pytest.mark.parametrize("vacio", [Salida(1, "no crontab for user"), Salida(1, "No Crontab for oracle"), Salida(1, "")])
def test_instalar_con_crontab_vacio(vacio):
    falso = CrontabFalso(lectura=vacio)
    ProgramadorCron(falso).instalar(7, DIARIO, RUTA)
    assert falso.escrituras == [f"# oracle-admin:7\n30 5 * * * {RUTA}\n"]


def test_comandos_y_entorno_de_lectura():
    falso = CrontabFalso()
    ProgramadorCron(falso).instalar(7, DIARIO, RUTA)
    assert falso.llamadas[0] == (["crontab", "-l"], None, {"LC_ALL": "C"})
    assert falso.llamadas[1][0] == ["crontab", "-"]


def test_prefijo_de_comando_configurable():
    falso = CrontabFalso()
    ProgramadorCron(falso, ("docker", "exec", "c", "crontab")).eliminar(7)
    assert falso.llamadas == [(["docker", "exec", "c", "crontab", "-l"], None, {"LC_ALL": "C"})]


def test_ruta_con_espacio_se_entrecomilla():
    falso = CrontabFalso()
    ProgramadorCron(falso).instalar(7, DIARIO, "/u01/mi ruta/p.sh")
    assert falso.texto == "# oracle-admin:7\n30 5 * * * '/u01/mi ruta/p.sh'\n"


def test_reinstalar_no_duplica_y_actualiza_la_frecuencia():
    falso = CrontabFalso()
    cron = ProgramadorCron(falso)
    cron.instalar(7, DIARIO, RUTA)
    cron.instalar(7, SEMANAL, RUTA)
    assert falso.texto == f"# oracle-admin:7\n0 2 * * 3 {RUTA}\n"
    cron.instalar(7, SEMANAL, RUTA)
    assert falso.texto == f"# oracle-admin:7\n0 2 * * 3 {RUTA}\n"


def test_instalar_conserva_lineas_ajenas_y_otros_ids():
    previo = f"{AJENA}\n# oracle-admin:3\n0 0 * * * /x/3.sh\n# comentario\n"
    falso = CrontabFalso(texto=previo)
    ProgramadorCron(falso).instalar(7, DIARIO, RUTA)
    assert falso.texto == previo + f"# oracle-admin:7\n30 5 * * * {RUTA}\n"


def test_id_con_prefijo_comun_no_se_confunde():
    previo = "# oracle-admin:70\n0 0 * * * /x/70.sh\n"
    falso = CrontabFalso(texto=previo)
    ProgramadorCron(falso).instalar(7, DIARIO, RUTA)
    assert falso.texto.startswith(previo)


def test_eliminar_quita_solo_ese_id():
    ajeno = f"{AJENA}\n# oracle-admin:3\n0 0 * * * /x/3.sh\n"
    falso = CrontabFalso(texto=f"{ajeno}# oracle-admin:7\n30 5 * * * {RUTA}\n")
    ProgramadorCron(falso).eliminar(7)
    assert falso.texto == ajeno


def test_eliminar_inexistente_no_escribe():
    falso = CrontabFalso(texto=f"{AJENA}\n")
    ProgramadorCron(falso).eliminar(7)
    assert falso.escrituras == []
    sin_crontab = CrontabFalso()
    ProgramadorCron(sin_crontab).eliminar(7)
    assert sin_crontab.escrituras == []


def test_error_de_lectura_distinto_de_no_crontab():
    falso = CrontabFalso(lectura=Salida(1, "permission denied"))
    with pytest.raises(OperacionEntornoFallida, match="permission denied"):
        ProgramadorCron(falso).instalar(7, DIARIO, RUTA)
    assert falso.escrituras == []
    with pytest.raises(OperacionEntornoFallida, match="permission denied"):
        ProgramadorCron(falso).eliminar(7)


@pytest.mark.parametrize("operacion", ["instalar", "eliminar"])
def test_error_de_escritura(operacion):
    falso = CrontabFalso(texto=f"# oracle-admin:7\n30 5 * * * {RUTA}\n", escritura=Salida(1, "bad crontab"))
    cron = ProgramadorCron(falso)
    with pytest.raises(OperacionEntornoFallida, match="bad crontab"):
        cron.instalar(7, DIARIO, RUTA) if operacion == "instalar" else cron.eliminar(7)


@pytest.mark.parametrize("operacion", ["instalar", "eliminar"])
def test_crontab_ausente_se_propaga(operacion):
    cron = ProgramadorCron(CrontabFalso(ausente=True))
    with pytest.raises(HerramientaNoDisponible):
        cron.instalar(7, DIARIO, RUTA) if operacion == "instalar" else cron.eliminar(7)
