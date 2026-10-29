import re
import stat
import tempfile
from pathlib import Path

import pytest

from src.services.entorno_local import EntornoLocal, SistemaLinux
from src.services.entorno_oracle import ComandoHerramienta, HerramientaNoDisponible, Salida


class ProcesoFalso:
    def __init__(self, error=None):
        self.error = error
        self.llamadas = []
        self.temporal = None

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append((args, entrada, variables))
        self.temporal = Path(args[-1].removeprefix("cmdfile="))
        # durante la llamada el temporal ya existe con el script y permisos 0600
        self.existia = self.temporal.exists()
        self.contenido = self.temporal.read_text()
        self.modo = stat.S_IMODE(self.temporal.stat().st_mode)
        if self.error:
            raise self.error
        return Salida(codigo=0, texto="salida de la herramienta")


def ejecutar(proceso, script="linea1\nlinea2\n", **opciones):
    entorno = EntornoLocal(SistemaLinux(), proceso)
    return entorno.ejecutar(
        ComandoHerramienta(
            "rman", lambda ruta: ["target", "/", f"cmdfile={ruta}"], script, prefijo="rman", extension=".rman", **opciones
        )
    )


def test_escribe_el_script_en_un_temporal_0600_del_directorio_temporal_del_so():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    assert proceso.existia
    assert proceso.contenido == "linea1\nlinea2\n"
    assert proceso.modo == 0o600
    assert proceso.temporal.parent == Path(tempfile.gettempdir())
    assert re.fullmatch(r"rman_[0-9a-f]{32}\.rman", proceso.temporal.name)


def test_lanza_la_herramienta_con_la_ruta_y_sin_el_contenido_en_los_argumentos():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    args, entrada, _ = proceso.llamadas[0]
    assert args == ["rman", "target", "/", f"cmdfile={proceso.temporal}"]
    assert entrada is None
    assert all("linea1" not in argumento for argumento in args)


def test_pasa_las_variables_al_proceso():
    proceso = ProcesoFalso()

    ejecutar(proceso, variables={"ORACLE_HOME": "/u01"})

    assert proceso.llamadas[0][2] == {"ORACLE_HOME": "/u01"}


def test_devuelve_la_salida_y_borra_el_temporal():
    proceso = ProcesoFalso()

    salida = ejecutar(proceso)

    assert salida == Salida(codigo=0, texto="salida de la herramienta")
    assert not proceso.temporal.exists()


def test_borra_el_temporal_si_la_herramienta_no_existe():
    proceso = ProcesoFalso(error=HerramientaNoDisponible("rman"))

    with pytest.raises(HerramientaNoDisponible):
        ejecutar(proceso)

    assert not proceso.temporal.exists()


def test_borra_el_temporal_si_el_proceso_lanza_una_excepcion():
    proceso = ProcesoFalso(error=RuntimeError("falla"))

    with pytest.raises(RuntimeError):
        ejecutar(proceso)

    assert not proceso.temporal.exists()
