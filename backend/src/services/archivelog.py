from src.services.errores_oracle import explicar_error
from src.services.expdp_runner import Ejecutor, ejecutar_con_archivo

FRA_DIRECTORIO = "/opt/oracle/oradata/fast_recovery_area"
FRA_TAMANO = "10G"

_SCRIPT = f"""WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SYSTEM SET db_recovery_file_dest_size={FRA_TAMANO} SCOPE=BOTH;
ALTER SYSTEM SET db_recovery_file_dest='{FRA_DIRECTORIO}' SCOPE=BOTH;
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


def activar_archivelog(contenedor: str, ejecutar: Ejecutor) -> str:
    salida = ejecutar_con_archivo(
        contenedor, "archivelog", _SCRIPT,
        lambda ruta: ["env", "ORACLE_SID=XE", "sqlplus", "-S", "/ as sysdba", f"@{ruta}"],
        ejecutar, extension=".sql",
    )
    if salida.codigo != 0:
        raise ArchivelogFallido(salida.texto)
    return salida.texto
