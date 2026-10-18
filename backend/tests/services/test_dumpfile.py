from datetime import datetime

import pytest

from src.services.dumpfile import NombreInvalido, construir_nombres

AHORA = datetime(2026, 10, 17, 15, 30, 45)


def test_agrega_fecha_y_hora_al_dmp_y_al_log():
    nombres = construir_nombres("ventas", AHORA)

    assert nombres.dmp == "ventas_20261017_153045.dmp"
    assert nombres.log == "ventas_20261017_153045.log"


@pytest.mark.parametrize("nombre", ["a", "Ventas_2026-q1", "x" * 50])
def test_acepta_letras_numeros_guion_y_guion_bajo_de_1_a_50(nombre):
    assert construir_nombres(nombre, AHORA).dmp.startswith(nombre + "_")


@pytest.mark.parametrize(
    "nombre",
    ["", "x" * 51, "con espacio", "../etc/passwd", "ruta/archivo", "a;b", "ñandú", "a.dmp"],
)
def test_rechaza_nombres_invalidos(nombre):
    with pytest.raises(NombreInvalido):
        construir_nombres(nombre, AHORA)
