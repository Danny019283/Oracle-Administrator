from src.services.expdp_runner import Salida
from src.services.rman_runner import ejecutar_rman

SCRIPT = "RUN {\n  BACKUP DATABASE;\n}\n"


class EjecutorFalso:
    def __init__(self, codigo_rman=0):
        self.codigo_rman = codigo_rman
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "rman" in args:
            return Salida(codigo=self.codigo_rman, texto="salida de rman")
        return Salida(codigo=0, texto="")


def test_ejecuta_rman_con_autenticacion_del_so_y_cmdfile_temporal():
    ejecutor = EjecutorFalso()

    ejecutar_rman("oracle-test", SCRIPT, ejecutor)

    ruta = ejecutor.llamadas[0][0][-1].split("cat > ")[1]
    assert ejecutor.llamadas[1][0] == [
        "docker", "exec", "oracle-test",
        "env", "ORACLE_SID=XE", "rman", "target", "/", f"cmdfile={ruta}",
    ]


def test_el_script_viaja_por_stdin_y_no_en_los_argumentos():
    ejecutor = EjecutorFalso()

    ejecutar_rman("oracle-test", SCRIPT, ejecutor)

    assert ejecutor.llamadas[0][1] == SCRIPT
    assert all("BACKUP" not in " ".join(args) for args, _ in ejecutor.llamadas)


def test_devuelve_la_salida_de_rman():
    salida = ejecutar_rman("oracle-test", SCRIPT, EjecutorFalso(codigo_rman=3))

    assert salida == Salida(codigo=3, texto="salida de rman")


def test_borra_el_archivo_temporal_al_terminar():
    ejecutor = EjecutorFalso()

    ejecutar_rman("oracle-test", SCRIPT, ejecutor)

    ruta = ejecutor.llamadas[0][0][-1].split("cat > ")[1]
    assert ejecutor.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]
