import sys

import pytest

from src.services.entorno_oracle import HerramientaNoDisponible, Salida
from src.services.procesos import ejecutar_proceso


def python(codigo):
    return [sys.executable, "-c", codigo]


def test_junta_stdout_y_stderr_con_strip_y_devuelve_el_codigo():
    salida = ejecutar_proceso(
        python("import sys; print(' fuera '); print('error', file=sys.stderr); sys.exit(3)")
    )

    assert salida == Salida(codigo=3, texto="fuera \nerror")


def test_pasa_la_entrada_por_stdin():
    salida = ejecutar_proceso(python("import sys; print(sys.stdin.read().upper())"), "hola")

    assert salida.texto == "HOLA"


def test_acepta_variables_de_entorno_y_conserva_las_del_proceso():
    salida = ejecutar_proceso(
        python("import os; print(os.environ['MI_VARIABLE'], 'PATH' in os.environ)"),
        variables={"MI_VARIABLE": "valor"},
    )

    assert salida.texto == "valor True"


def test_ejecutable_inexistente_lanza_herramienta_no_disponible_que_nombra_la_herramienta():
    with pytest.raises(HerramientaNoDisponible, match="herramienta-que-no-existe") as error:
        ejecutar_proceso(["herramienta-que-no-existe", "-x"])

    assert error.value.__suppress_context__
    assert "Traceback" not in str(error.value)


def test_ejecutable_sin_permiso_lanza_herramienta_no_disponible(tmp_path):
    sin_permiso = tmp_path / "sin_permiso"
    sin_permiso.write_text("#!/bin/sh\n")

    with pytest.raises(HerramientaNoDisponible, match="sin_permiso"):
        ejecutar_proceso([str(sin_permiso)])
