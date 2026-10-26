import pytest

from src.services.expdp_runner import Salida, ejecutar_con_archivo


class EjecutorFalso:
    def __init__(self, codigo_comando=0):
        self.codigo_comando = codigo_comando
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if args[:3] == ["docker", "exec", "oracle-test"] and "cat" not in args and "rm" not in args:
            return Salida(codigo=self.codigo_comando, texto="salida del comando")
        return Salida(codigo=0, texto="")


def ejecutar(ejecutor, contenido="linea1\nlinea2\n"):
    return ejecutar_con_archivo(
        "oracle-test",
        "rman",
        contenido,
        lambda ruta: ["rman", f"cmdfile={ruta}"],
        ejecutor,
    )


def test_escribe_el_contenido_por_stdin_con_umask_restrictivo():
    ejecutor = EjecutorFalso()

    ejecutar(ejecutor, "linea1\nlinea2\n")

    args, entrada = ejecutor.llamadas[0]
    assert args[:5] == ["docker", "exec", "-i", "oracle-test", "sh"]
    assert args[-1].startswith("umask 077; cat > /tmp/rman_")
    assert entrada == "linea1\nlinea2\n"


def test_el_comando_recibe_la_ruta_del_archivo_temporal():
    ejecutor = EjecutorFalso()

    ejecutar(ejecutor)

    ruta = ejecutor.llamadas[0][0][-1].split("cat > ")[1]
    assert ejecutor.llamadas[1][0] == ["docker", "exec", "oracle-test", "rman", f"cmdfile={ruta}"]


def test_devuelve_la_salida_del_comando():
    salida = ejecutar(EjecutorFalso(codigo_comando=7))

    assert salida == Salida(codigo=7, texto="salida del comando")


def test_borra_el_archivo_temporal_al_terminar():
    ejecutor = EjecutorFalso()

    ejecutar(ejecutor)

    ruta = ejecutor.llamadas[0][0][-1].split("cat > ")[1]
    assert ejecutor.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_borra_el_archivo_temporal_aunque_el_comando_lance_una_excepcion():
    class EjecutorQueFalla(EjecutorFalso):
        def __call__(self, args, entrada=None):
            if "rman" in args:
                self.llamadas.append((args, entrada))
                raise RuntimeError("docker no responde")
            return super().__call__(args, entrada)

    ejecutor = EjecutorQueFalla()

    with pytest.raises(RuntimeError):
        ejecutar(ejecutor)

    assert ejecutor.llamadas[-1][0][3:5] == ["rm", "-f"]
