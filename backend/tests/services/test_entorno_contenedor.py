import re

import pytest

from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_oracle import Salida


class ProcesoFalso:
    def __init__(self, codigo_herramienta=0, falla=False):
        self.codigo_herramienta = codigo_herramienta
        self.falla = falla
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "rman" in args and "cat" not in args:
            if self.falla:
                raise RuntimeError("docker no responde")
            return Salida(codigo=self.codigo_herramienta, texto="salida de la herramienta")
        return Salida(codigo=0, texto="contenido del archivo")


def ejecutar(proceso, script="linea1\nlinea2\n", **opciones):
    entorno = EntornoContenedor("oracle-test", proceso)
    return entorno.ejecutar_herramienta(
        "rman", lambda ruta: ["target", "/", f"cmdfile={ruta}"], script, prefijo="rman", extension=".rman", **opciones
    )


def test_escribe_el_script_por_stdin_con_umask_restrictivo_y_fuera_de_los_argumentos():
    proceso = ProcesoFalso()

    ejecutar(proceso, "linea1\nlinea2\n")

    args, entrada = proceso.llamadas[0]
    assert args[:5] == ["docker", "exec", "-i", "oracle-test", "sh"]
    assert args[-1].startswith("umask 077; cat > /tmp/rman_")
    assert entrada == "linea1\nlinea2\n"
    assert all("linea1" not in argumento for args, _ in proceso.llamadas for argumento in args)


def test_el_temporal_tiene_la_forma_prefijo_uuid_extension():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    assert re.fullmatch(r"umask 077; cat > /tmp/rman_[0-9a-f]{32}\.rman", proceso.llamadas[0][0][-1])


def test_la_herramienta_recibe_la_ruta_del_temporal():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[1][0] == ["docker", "exec", "oracle-test", "rman", "target", "/", f"cmdfile={ruta}"]


def test_con_variables_la_herramienta_se_ejecuta_con_env():
    proceso = ProcesoFalso()

    ejecutar(proceso, variables={"ORACLE_SID": "XE"})

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[1][0] == [
        "docker", "exec", "oracle-test", "env", "ORACLE_SID=XE", "rman", "target", "/", f"cmdfile={ruta}",
    ]


def test_devuelve_la_salida_de_la_herramienta():
    salida = ejecutar(ProcesoFalso(codigo_herramienta=7))

    assert salida == Salida(codigo=7, texto="salida de la herramienta")


def test_borra_el_temporal_con_rm_f_al_terminar():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_borra_el_temporal_aunque_la_herramienta_lance_una_excepcion():
    proceso = ProcesoFalso(falla=True)

    with pytest.raises(RuntimeError):
        ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_leer_archivo_ejecuta_cat_dentro_del_contenedor():
    proceso = ProcesoFalso()

    texto = EntornoContenedor("oracle-test", proceso).leer_archivo(EntornoContenedor.tipo_ruta("/u01/log.log"))

    assert proceso.llamadas == [(["docker", "exec", "oracle-test", "cat", "/u01/log.log"], None)]
    assert texto == "contenido del archivo"
