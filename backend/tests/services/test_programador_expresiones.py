import pytest

from src.services.politica_respaldo import Programacion
from src.services.programador_tareas import (
    argumentos_schtasks,
    expresion_cron,
    marca_cron,
    nombre_tarea,
)


def prog(frecuencia, hora="05:30", dia=None, n=2, politica="FULL"):
    if frecuencia == "HORAS":
        politica, hora = "TRANSACCIONAL", None
    return Programacion("p", "BACKUP", politica, frecuencia, hora, dia, n)


@pytest.mark.parametrize(
    "p, esperado",
    [
        (prog("DIARIO"), "30 5 * * *"),
        (prog("DIARIO", "00:00"), "0 0 * * *"),
        (prog("DIARIO", "23:59"), "59 23 * * *"),
        (prog("SEMANAL"), "30 5 * * 0"),
        (prog("SEMANAL", "23:59", 6), "59 23 * * 6"),
        (prog("SEMANAL", "00:00", 3), "0 0 * * 3"),
        (prog("MENSUAL"), "30 5 1 * *"),
        (prog("MENSUAL", "00:00", 28), "0 0 28 * *"),
        (prog("HORAS", n=2), "0 */2 * * *"),
        (prog("HORAS", n=23), "0 */23 * * *"),
    ],
)
def test_expresion_cron(p, esperado):
    assert expresion_cron(p) == esperado


RUTA = r"C:\ruta con espacio\x.bat"
BASE = ["/Create", "/TN", "OracleAdmin_7", "/TR", f'"{RUTA}"']
FIN = ["/RU", "SYSTEM", "/F"]


@pytest.mark.parametrize(
    "p, esperado",
    [
        (prog("DIARIO"), ["/SC", "DAILY", "/ST", "05:30"]),
        (prog("SEMANAL"), ["/SC", "WEEKLY", "/ST", "05:30", "/D", "SUN"]),
        (prog("SEMANAL", "23:59", 6), ["/SC", "WEEKLY", "/ST", "23:59", "/D", "SAT"]),
        (prog("SEMANAL", "00:00", 1), ["/SC", "WEEKLY", "/ST", "00:00", "/D", "MON"]),
        (prog("MENSUAL"), ["/SC", "MONTHLY", "/ST", "05:30", "/D", "1"]),
        (prog("MENSUAL", "00:00", 28), ["/SC", "MONTHLY", "/ST", "00:00", "/D", "28"]),
        (prog("HORAS", n=2), ["/SC", "HOURLY", "/ST", "00:00", "/MO", "2"]),
        (prog("HORAS", n=23), ["/SC", "HOURLY", "/ST", "00:00", "/MO", "23"]),
    ],
)
def test_argumentos_schtasks(p, esperado):
    assert argumentos_schtasks(p, 7, RUTA) == BASE + esperado + FIN


def test_dias_de_la_semana_schtasks():
    dias = [argumentos_schtasks(prog("SEMANAL", dia=d), 1, "a.bat")[-4] for d in range(7)]
    assert dias == ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]


def test_nombre_y_marca():
    assert nombre_tarea(12) == "OracleAdmin_12"
    assert marca_cron(12) == "# oracle-admin:12"


@pytest.mark.parametrize("malo", [0, -1, "1", None, 1.0, True])
def test_id_invalido(malo):
    with pytest.raises(ValueError):
        nombre_tarea(malo)
    with pytest.raises(ValueError):
        marca_cron(malo)
    with pytest.raises(ValueError):
        argumentos_schtasks(prog("DIARIO"), malo, "a.bat")


@pytest.mark.parametrize("f", [prog("DIARIO", politica="OTRA"), Programacion("p", "B", "FULL", "ANUAL", "05:30")])
def test_politica_o_frecuencia_desconocida(f):
    with pytest.raises(ValueError):
        expresion_cron(f)
    with pytest.raises(ValueError):
        argumentos_schtasks(f, 1, "a.bat")
