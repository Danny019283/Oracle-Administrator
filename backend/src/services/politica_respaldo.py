import re
import shlex
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePath, PureWindowsPath

from src.services.respaldo import errores_destino

POLITICAS = ("FULL", "INCREMENTAL", "TRANSACCIONAL")
FRECUENCIAS = ("DIARIO", "SEMANAL", "MENSUAL", "HORAS")
_HORA = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


@dataclass(frozen=True)
class Programacion:
    nombre: str
    directorio: str
    politica: str
    frecuencia: str
    hora: str | None = None  # HH:MM; no aplica con HORAS (minuto 0)
    dia: int | None = None  # None = por defecto: 0 (domingo) semanal, 1 mensual
    intervalo_horas: int = 2

    @property
    def dia_efectivo(self) -> int:
        if self.dia is not None:
            return self.dia
        return 1 if self.frecuencia == "MENSUAL" else 0


def _entero_en(valor, minimo: int, maximo: int) -> bool:
    return type(valor) is int and minimo <= valor <= maximo


def validar_programacion(prog: Programacion, directorios: Collection[str]) -> list[str]:
    nombre = prog.nombre if isinstance(prog.nombre, str) else ""
    errores = [
        "Debes ingresar un nombre para la programación" if e == "Debes ingresar un nombre de dumpfile" else e
        for e in errores_destino(prog.directorio, nombre, directorios)
    ]

    if prog.politica not in POLITICAS:
        errores.append("La política no es válida (FULL, INCREMENTAL o TRANSACCIONAL)")
    if prog.frecuencia not in FRECUENCIAS:
        errores.append("La frecuencia no es válida (DIARIO, SEMANAL, MENSUAL o HORAS)")
        return errores

    if prog.frecuencia == "HORAS":
        if prog.politica != "TRANSACCIONAL":
            errores.append("La frecuencia por horas solo vale con la política TRANSACCIONAL")
        if not _entero_en(prog.intervalo_horas, 1, 23):
            errores.append("Las horas entre respaldos deben ser un número de 1 a 23")
        return errores

    if not isinstance(prog.hora, str) or not _HORA.fullmatch(prog.hora):
        errores.append("La hora debe tener el formato HH:MM de 24 horas")
    if prog.frecuencia == "SEMANAL" and not _entero_en(prog.dia_efectivo, 0, 6):
        errores.append("El día de la semana debe ser de 0 (domingo) a 6 (sábado)")
    if prog.frecuencia == "MENSUAL" and not _entero_en(prog.dia_efectivo, 1, 28):
        errores.append("El día del mes debe ser de 1 a 28")
    return errores


_CUERPOS_RMAN = {
    "FULL": """  BACKUP INCREMENTAL LEVEL 0
  DATABASE
  TAG 'PROG_FULL_L0'
  FORMAT '{f}';
  CROSSCHECK BACKUP;
  CROSSCHECK ARCHIVELOG ALL;
  DELETE NOPROMPT OBSOLETE;
""",
    "INCREMENTAL": """  BACKUP INCREMENTAL LEVEL 1
  DATABASE
  TAG 'PROG_INCREMENTAL_L1'
  FORMAT '{f}';
  BACKUP ARCHIVELOG ALL
  FORMAT '{f}'
  DELETE INPUT;
""",
    "TRANSACCIONAL": """  SQL 'ALTER SYSTEM SWITCH LOGFILE';
  BACKUP ARCHIVELOG ALL
  TAG 'PROG_TRANSACCIONAL'
  FORMAT '{f}'
  DELETE INPUT;
""",
}


def script_rman(politica: str, ruta_destino: PurePath) -> str:
    """`&1` lo sustituye RMAN (`using <base>`), así el script no lleva nombre ni fecha."""
    if politica not in _CUERPOS_RMAN:
        raise ValueError(f"Política desconocida: {politica}")
    cuerpo = _CUERPOS_RMAN[politica].format(f=ruta_destino / "&1_%d_%s_%p.dbf")
    return f"RUN {{\n  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;\n{cuerpo}  RELEASE CHANNEL ch1;\n}}\n"


_NOMBRE = re.compile(r"[A-Za-z0-9_-]+")
_SID = re.compile(r"[A-Za-z0-9_]+")
# ORACLE_HOME absoluto (POSIX o con unidad) sin caracteres con significado para sh o cmd
_HOME = re.compile(r"(/|[A-Za-z]:[\\/])[^\"'\r\n$`%&|<>^!;]*")


def extension_envoltorio(ruta: PurePath) -> str:
    return ".bat" if isinstance(ruta, PureWindowsPath) else ".sh"


def envoltorio(nombre: str, sid: str, oracle_home: str, ruta_rman: PurePath, ruta_destino: PurePath) -> str:
    """Lanza RMAN con `target /` (sin contraseñas); el cron/schtasks no heredan el entorno."""
    if not (isinstance(nombre, str) and _NOMBRE.fullmatch(nombre)):
        raise ValueError("Nombre no válido para el envoltorio")
    if not (isinstance(sid, str) and _SID.fullmatch(sid)):
        raise ValueError("ORACLE_SID no válido")
    if not (isinstance(oracle_home, str) and _HOME.fullmatch(oracle_home)):
        raise ValueError("ORACLE_HOME no válido")
    # `using` lleva la base entre comillas simples para RMAN: sin ellas rechaza el guion (RMAN-00552/02001)
    if extension_envoltorio(ruta_rman) == ".sh":
        return (
            "#!/bin/sh\n"
            f"export ORACLE_SID={shlex.quote(sid)}\n"
            f"export ORACLE_HOME={shlex.quote(oracle_home)}\n"
            'export PATH="$ORACLE_HOME/bin:$PATH"\n'
            f'BASE="{nombre}_$(date +%Y%m%d_%H%M%S)"\n'
            f'rman target / cmdfile={ruta_rman} log={ruta_destino}/$BASE.log using "\'$BASE\'"\n'
            "exit $?\n"
        )
    lineas = [
        "@echo off",
        f"set ORACLE_SID={sid}",
        f"set ORACLE_HOME={oracle_home}",
        r"set PATH=%ORACLE_HOME%\bin;%PATH%",
        """for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i""",
        f"set BASE={nombre}_%TS%",
        f'rman target / cmdfile="{ruta_rman}" log="{ruta_destino}\\%BASE%.log" using \'%BASE%\'',
        "exit /b %errorlevel%",
        "",
    ]
    return "\r\n".join(lineas)
