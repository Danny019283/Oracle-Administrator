from pathlib import PurePath, PurePosixPath

from src.services.entorno_oracle import EntornoOracle, OperacionEntornoFallida
from src.services.errores_oracle import explicar_error

FRA_DIRECTORIO = PurePosixPath("/opt/oracle/oradata/fast_recovery_area")
FRA_TAMANO = "10G"


def _script(fra: PurePath) -> str:
    return f"""WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SYSTEM SET db_recovery_file_dest_size={FRA_TAMANO} SCOPE=BOTH;
ALTER SYSTEM SET db_recovery_file_dest='{fra}' SCOPE=BOTH;
SHUTDOWN IMMEDIATE
STARTUP MOUNT
ALTER DATABASE ARCHIVELOG;
ALTER DATABASE OPEN;
EXIT
"""


class ArchivelogFallido(Exception):
    def __init__(self, log: str):
        super().__init__("No se pudo activar ARCHIVELOG")
        self.log = log
        self.explicacion = explicar_error(log)


def activar_archivelog(entorno: EntornoOracle, fra: PurePath) -> str:
    try:
        entorno.crear_carpeta(fra)
    except OperacionEntornoFallida as error:
        raise ArchivelogFallido(str(error)) from error
    salida = entorno.ejecutar_herramienta(
        "sqlplus", lambda ruta: ["-S", "/ as sysdba", f"@{ruta}"], _script(fra),
        prefijo="archivelog", extension=".sql", variables={"ORACLE_SID": "XE"},
    )
    if salida.codigo != 0:
        raise ArchivelogFallido(salida.texto)
    return salida.texto
