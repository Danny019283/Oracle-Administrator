import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePath

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
    errores = errores_destino(prog.directorio, nombre, directorios)

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
