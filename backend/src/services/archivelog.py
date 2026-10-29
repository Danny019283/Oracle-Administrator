from pathlib import PurePath, PurePosixPath

import oracledb

from src.services.entorno_oracle import ComandoHerramienta, EntornoOracle, OperacionEntornoFallida
from src.services.errores_oracle import explicar_error
from src.services.tablespaces import TablespaceInvalido, carpeta_datafiles

FRA_DIRECTORIO = PurePosixPath("/opt/oracle/oradata/fast_recovery_area")
FRA_TAMANO = "10G"
FRA_CARPETA = "fast_recovery_area"


def derivar_fra(consulta, tipo_ruta: type[PurePath]) -> PurePath | None:
    """FRA junto a la carpeta de datafiles de SYSTEM; None si Oracle no da esa carpeta."""
    try:
        carpeta = carpeta_datafiles(consulta)
    except (TablespaceInvalido, oracledb.Error):
        return None
    return tipo_ruta(carpeta).parent / FRA_CARPETA


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


def activar_archivelog(entorno: EntornoOracle, fra: PurePath, sid: str) -> str:
    try:
        entorno.crear_carpeta(fra)
    except OperacionEntornoFallida as error:
        raise ArchivelogFallido(str(error)) from error
    salida = entorno.ejecutar(
        ComandoHerramienta(
            "sqlplus", lambda ruta: ["-S", "/ as sysdba", f"@{ruta}"], _script(fra),
            prefijo="archivelog", extension=".sql", variables={"ORACLE_SID": sid},
        )
    )
    if salida.codigo != 0:
        raise ArchivelogFallido(salida.texto)
    return salida.texto
