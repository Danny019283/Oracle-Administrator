import pytest

from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida, Salida
from src.services.politica_respaldo import Programacion
from src.services.programador_tareas import ProgramadorCron, ProgramadorCronContenedor, ProgramadorTareas

DIARIO = Programacion("p", "BACKUP", "FULL", "DIARIO", "05:30")
SEMANAL = Programacion("p", "BACKUP", "FULL", "SEMANAL", "02:00", 3)
RUTA = "/u01/backup/scripts_programados/p.sh"
CROND = "pgrep -x crond >/dev/null 2>&1 || crond"


class ContenedorFalso:
    """Ejecutor falso: crontab del usuario oracle dentro del contenedor y comprobación de crond."""

    def __init__(self, texto=None, lectura=None, escritura=None, crond=None, ausente=False, cli="docker"):
        self.cli = cli
        self.texto = texto  # None = sin crontab
        self.lectura = lectura
        self.escritura = escritura
        self.crond = crond  # Salida forzada para la comprobación de crond
        self.ausente = ausente
        self.llamadas = []
        self.escrituras = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append((list(args), entrada, variables))
        if self.ausente:
            raise HerramientaNoDisponible(args[0])
        if args[-3:-1] == ["sh", "-c"]:
            return self.crond or Salida(0, "")
        if args[-1] == "-l":
            if self.lectura:
                return self.lectura
            if self.texto is None:
                return Salida(1, "no crontab for oracle")
            return Salida(0, self.texto.rstrip("\n"))
        if self.escritura:
            return self.escritura
        self.texto = entrada
        self.escrituras.append(entrada)
        return Salida(0, "")

    @property
    def comandos(self):
        return [a for a, _, _ in self.llamadas]


def programador(falso, cli="docker"):
    return ProgramadorCronContenedor("oracle21c", falso, cli)


def test_es_un_programador_cron():
    assert issubclass(ProgramadorCronContenedor, ProgramadorCron)
    assert issubclass(ProgramadorCronContenedor, ProgramadorTareas)


@pytest.mark.parametrize("cli", ["docker", "podman"])
def test_comandos_exactos_y_orden(cli):
    falso = ContenedorFalso()
    programador(falso, cli).instalar(7, DIARIO, RUTA)
    assert falso.comandos == [
        [cli, "exec", "-u", "root", "oracle21c", "sh", "-c", CROND],
        [cli, "exec", "-u", "root", "oracle21c", "crontab", "-u", "oracle", "-l"],
        [cli, "exec", "-i", "-u", "root", "oracle21c", "crontab", "-u", "oracle", "-"],
    ]
    assert falso.llamadas[1][1:] == (None, {"LC_ALL": "C"})
    assert falso.escrituras == [f"# oracle-admin:7\n30 5 * * * {RUTA}\n"]


def test_la_lectura_no_lleva_i():
    falso = ContenedorFalso(texto=f"# oracle-admin:7\n30 5 * * * {RUTA}\n")
    programador(falso).eliminar(7)
    lectura, escritura = falso.comandos[1], falso.comandos[2]
    assert "-i" not in lectura and lectura[-1] == "-l"
    assert "-i" in escritura and escritura[-1] == "-"


def test_usuario_oracle_configurable():
    falso = ContenedorFalso()
    ProgramadorCronContenedor("c", falso, "docker", "ora").instalar(7, DIARIO, RUTA)
    assert falso.comandos[1] == ["docker", "exec", "-u", "root", "c", "crontab", "-u", "ora", "-l"]
    assert falso.comandos[2] == ["docker", "exec", "-i", "-u", "root", "c", "crontab", "-u", "ora", "-"]


def test_eliminar_comprueba_crond_antes_de_leer_y_escribe():
    falso = ContenedorFalso(texto=f"# oracle-admin:7\n30 5 * * * {RUTA}\n")
    programador(falso).eliminar(7)
    assert falso.comandos[0][-3:] == ["sh", "-c", CROND]
    assert falso.texto == "\n"


@pytest.mark.parametrize("operacion", ["instalar", "eliminar"])
def test_fallo_de_crond_no_toca_el_crontab(operacion):
    falso = ContenedorFalso(texto=f"# oracle-admin:7\n30 5 * * * {RUTA}\n", crond=Salida(1, "crond: no such file"))
    cron = programador(falso)
    with pytest.raises(OperacionEntornoFallida, match="crond: no such file"):
        cron.instalar(7, DIARIO, RUTA) if operacion == "instalar" else cron.eliminar(7)
    assert len(falso.llamadas) == 1
    assert falso.escrituras == []


def test_instalar_idempotente():
    falso = ContenedorFalso()
    cron = programador(falso)
    cron.instalar(7, DIARIO, RUTA)
    cron.instalar(7, SEMANAL, RUTA)
    cron.instalar(7, SEMANAL, RUTA)
    assert falso.texto == f"# oracle-admin:7\n0 2 * * 3 {RUTA}\n"


def test_eliminar_inexistente_no_escribe():
    falso = ContenedorFalso(texto="0 1 * * * /usr/bin/otra-cosa\n")
    programador(falso).eliminar(7)
    sin_crontab = ContenedorFalso()
    programador(sin_crontab).eliminar(7)
    assert falso.escrituras == [] and sin_crontab.escrituras == []


def test_error_de_lectura_y_de_escritura():
    lee = ContenedorFalso(lectura=Salida(1, "permission denied"))
    with pytest.raises(OperacionEntornoFallida, match="permission denied"):
        programador(lee).instalar(7, DIARIO, RUTA)
    assert lee.escrituras == []
    escribe = ContenedorFalso(escritura=Salida(1, "bad crontab"))
    with pytest.raises(OperacionEntornoFallida, match="bad crontab"):
        programador(escribe).instalar(7, DIARIO, RUTA)


@pytest.mark.parametrize("operacion", ["instalar", "eliminar"])
def test_cli_ausente_se_propaga(operacion):
    cron = programador(ContenedorFalso(ausente=True))
    with pytest.raises(HerramientaNoDisponible):
        cron.instalar(7, DIARIO, RUTA) if operacion == "instalar" else cron.eliminar(7)


# Endurecimiento de _sin: crontab editado a mano tras la marca propia

TRABAJO7 = f"30 5 * * * {RUTA}"


def test_marca_seguida_de_linea_en_blanco_no_borra_la_siguiente():
    falso = ContenedorFalso(texto=f"# oracle-admin:7\n\n0 1 * * * /otra\n")
    programador(falso).eliminar(7)
    assert falso.texto == "\n0 1 * * * /otra\n"


def test_marca_seguida_de_comentario_conserva_el_comentario():
    falso = ContenedorFalso(texto="# oracle-admin:7\n# nota mia\n0 1 * * * /otra\n")
    programador(falso).eliminar(7)
    assert falso.texto == "# nota mia\n0 1 * * * /otra\n"


def test_marca_seguida_de_otra_marca_no_deja_huerfano_al_otro_id():
    falso = ContenedorFalso(texto=f"# oracle-admin:7\n# oracle-admin:3\n0 0 * * * /x/3.sh\n")
    programador(falso).eliminar(7)
    assert falso.texto == "# oracle-admin:3\n0 0 * * * /x/3.sh\n"


def test_marca_con_espacios_al_final_se_reconoce():
    falso = ContenedorFalso(texto=f"# oracle-admin:7  \n{TRABAJO7}\n0 1 * * * /otra\n")
    programador(falso).eliminar(7)
    assert falso.texto == "0 1 * * * /otra\n"


def test_instalar_con_marca_sin_trabajo_no_duplica_ni_borra_ajenas():
    falso = ContenedorFalso(texto="# oracle-admin:7\n\n0 1 * * * /otra\n")
    programador(falso).instalar(7, DIARIO, RUTA)
    assert falso.texto == f"\n0 1 * * * /otra\n# oracle-admin:7\n{TRABAJO7}\n"
