from dataclasses import FrozenInstanceError, replace

import pytest

from src.services.politica_respaldo import Programacion, validar_programacion

DIRECTORIOS = ["RESPALDO", "OTRO"]
BASE = Programacion("nocturno", "RESPALDO", "FULL", "DIARIO", "02:30")


def errores(**cambios):
    return validar_programacion(replace(BASE, **cambios), DIRECTORIOS)


def test_valores_por_defecto():
    prog = Programacion("a", "RESPALDO", "FULL", "DIARIO", "00:00")
    assert prog.dia is None and prog.dia_efectivo == 0 and prog.intervalo_horas == 2
    assert replace(prog, frecuencia="MENSUAL").dia_efectivo == 1
    with pytest.raises(FrozenInstanceError):
        prog.nombre = "otro"


@pytest.mark.parametrize(
    "cambios",
    [
        {},
        {"nombre": "Mi-resp_2"},
        {"politica": "INCREMENTAL", "hora": "23:59"},
        {"frecuencia": "SEMANAL"},
        {"frecuencia": "SEMANAL", "dia": 6},
        {"frecuencia": "MENSUAL"},
        {"frecuencia": "MENSUAL", "dia": 28},
        {"politica": "TRANSACCIONAL", "frecuencia": "HORAS", "hora": None},
        {"politica": "TRANSACCIONAL", "frecuencia": "HORAS", "hora": None, "intervalo_horas": 23},
        {"politica": "TRANSACCIONAL", "frecuencia": "HORAS", "hora": None, "intervalo_horas": 1},
        {"politica": "TRANSACCIONAL", "frecuencia": "DIARIO"},
        # los campos de otra frecuencia no se validan
        {"dia": 99, "intervalo_horas": 0},
    ],
)
def test_validos(cambios):
    assert errores(**cambios) == []


@pytest.mark.parametrize(
    "cambios, texto",
    [
        ({"nombre": ""}, "nombre"),
        ({"nombre": "con espacio"}, ""),
        ({"nombre": "../x"}, ""),
        ({"directorio": ""}, "directorio"),
        ({"directorio": "NOEXISTE"}, "NOEXISTE"),
        ({"politica": "OTRA"}, "política"),
        ({"politica": ""}, "política"),
        ({"frecuencia": "ANUAL"}, "frecuencia"),
        ({"hora": "24:00"}, "hora"),
        ({"hora": "7:5"}, "hora"),
        ({"hora": "ab"}, "hora"),
        ({"hora": "12:60"}, "hora"),
        ({"hora": None}, "hora"),
        ({"frecuencia": "SEMANAL", "dia": 7}, "semana"),
        ({"frecuencia": "SEMANAL", "dia": -1}, "semana"),
        ({"frecuencia": "MENSUAL", "dia": 0}, "mes"),
        ({"frecuencia": "MENSUAL", "dia": 29}, "mes"),
        ({"frecuencia": "SEMANAL", "dia": "1"}, "semana"),
        ({"frecuencia": "HORAS"}, "TRANSACCIONAL"),
        ({"politica": "TRANSACCIONAL", "frecuencia": "HORAS", "intervalo_horas": 0}, "horas"),
        ({"politica": "TRANSACCIONAL", "frecuencia": "HORAS", "intervalo_horas": 24}, "horas"),
        ({"politica": "INCREMENTAL", "frecuencia": "HORAS", "intervalo_horas": 3}, "TRANSACCIONAL"),
    ],
)
def test_invalidos(cambios, texto):
    resultado = errores(**cambios)
    assert resultado and all(isinstance(e, str) for e in resultado)
    assert any(texto in e for e in resultado)


def test_un_error_por_problema():
    assert len(errores(nombre="", directorio="", politica="X", hora="ab")) == 4


def test_no_lanza_con_valores_raros():
    assert errores(politica=None, frecuencia=None, hora=5, nombre=None)
