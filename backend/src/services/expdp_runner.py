import os
from dataclasses import dataclass, field

from src.services.entorno_oracle import ComandoHerramienta, EntornoOracle, Salida

__all__ = ["Conexion", "Salida", "ejecutar_expdp"]


@dataclass(frozen=True)
class Conexion:
    usuario: str
    password: str
    servicio: str
    host: str = field(default_factory=lambda: os.environ.get("ORACLE_HOST", "localhost"))
    puerto: int = field(default_factory=lambda: int(os.environ.get("ORACLE_PORT", "1521")))
    sysdba: bool = False


def _ejecutar_data_pump(herramienta: str, entorno: EntornoOracle, conexion: Conexion, parametros: list[str]) -> Salida:
    credenciales = f"{conexion.usuario}/{conexion.password}@{conexion.host}:{conexion.puerto}/{conexion.servicio}"
    # expdp/impdp rechazan «AS SYSDBA» sin comillas en el parfile (LRM-00112).
    userid = f'USERID="{credenciales} AS SYSDBA"' if conexion.sysdba else f"USERID={credenciales}"
    contenido = "\n".join([userid, *parametros]) + "\n"
    return entorno.ejecutar(
        ComandoHerramienta(herramienta, lambda ruta: [f"PARFILE={ruta}"], contenido, prefijo=herramienta, extension=".par")
    )


def ejecutar_expdp(entorno: EntornoOracle, conexion: Conexion, parametros: list[str]) -> Salida:
    return _ejecutar_data_pump("expdp", entorno, conexion, parametros)
