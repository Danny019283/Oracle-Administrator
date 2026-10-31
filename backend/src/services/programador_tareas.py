from src.services.politica_respaldo import FRECUENCIAS, POLITICAS, Programacion

_DIAS = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
_SC = {"DIARIO": "DAILY", "SEMANAL": "WEEKLY", "MENSUAL": "MONTHLY", "HORAS": "HOURLY"}


def _id_valido(id_programacion) -> int:
    if type(id_programacion) is not int or id_programacion < 1:
        raise ValueError("El id de la programación debe ser un entero mayor o igual que 1")
    return id_programacion


def _comprobar(prog: Programacion) -> None:
    if prog.politica not in POLITICAS:
        raise ValueError(f"Política desconocida: {prog.politica!r}")
    if prog.frecuencia not in FRECUENCIAS:
        raise ValueError(f"Frecuencia desconocida: {prog.frecuencia!r}")


def nombre_tarea(id_programacion: int) -> str:
    return f"OracleAdmin_{_id_valido(id_programacion)}"


def marca_cron(id_programacion: int) -> str:
    return f"# oracle-admin:{_id_valido(id_programacion)}"


def _hora_minuto(prog: Programacion) -> tuple[int, int]:
    hora, minuto = prog.hora.split(":")
    return int(hora), int(minuto)


def expresion_cron(prog: Programacion) -> str:
    _comprobar(prog)
    if prog.frecuencia == "HORAS":
        return f"0 */{prog.intervalo_horas} * * *"
    h, m = _hora_minuto(prog)
    if prog.frecuencia == "DIARIO":
        return f"{m} {h} * * *"
    if prog.frecuencia == "SEMANAL":
        return f"{m} {h} * * {prog.dia_efectivo}"
    return f"{m} {h} {prog.dia_efectivo} * *"


def argumentos_schtasks(prog: Programacion, id_programacion: int, ruta_script: str) -> list[str]:
    _comprobar(prog)
    args = ["/Create", "/TN", nombre_tarea(id_programacion), "/TR", f'"{ruta_script}"']
    args += ["/SC", _SC[prog.frecuencia], "/ST", "00:00" if prog.frecuencia == "HORAS" else prog.hora]
    if prog.frecuencia == "SEMANAL":
        args += ["/D", _DIAS[prog.dia_efectivo]]
    elif prog.frecuencia == "MENSUAL":
        args += ["/D", str(prog.dia_efectivo)]
    elif prog.frecuencia == "HORAS":
        args += ["/MO", str(prog.intervalo_horas)]
    return args + ["/RU", "SYSTEM", "/F"]
