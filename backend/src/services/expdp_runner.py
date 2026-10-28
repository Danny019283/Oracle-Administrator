import os
from collections.abc import Callable
from dataclasses import dataclass, field

from src.services.entorno_contenedor import EntornoContenedor, Ejecutor
from src.services.entorno_oracle import EntornoOracle, Salida

__all__ = ["Conexion", "Ejecutor", "Salida", "ejecutar_con_archivo", "ejecutar_expdp"]


@dataclass(frozen=True)
class Conexion:
    usuario: str
    password: str
    servicio: str
    host: str = field(default_factory=lambda: os.environ.get("ORACLE_HOST", "localhost"))
    puerto: int = field(default_factory=lambda: int(os.environ.get("ORACLE_PORT", "1521")))
    sysdba: bool = False


def ejecutar_con_archivo(
    contenedor: str,
    prefijo: str,
    contenido: str,
    comando: Callable[[str], list[str]],
    ejecutar: Ejecutor,
    extension: str = "",
) -> Salida:
    """Escribe `contenido` por stdin en un archivo temporal del contenedor
    (para que no aparezca en los argumentos del proceso), ejecuta el comando
    que lo usa y siempre lo borra."""
    entorno = EntornoContenedor(contenedor, ejecutar)
    variables, nombre, n_prefijo = _separar_comando(comando(""))
    return entorno.ejecutar_herramienta(
        nombre, lambda ruta: comando(ruta)[n_prefijo:], contenido,
        prefijo=prefijo, extension=extension, variables=variables,
    )


def _separar_comando(comando: list[str]) -> tuple[dict[str, str], str, int]:
    """Traduce el prefijo `env K=V …` del comando a variables; devuelve también
    la herramienta y cuántos elementos preceden a sus argumentos."""
    variables: dict[str, str] = {}
    posicion = 0
    if comando[0] == "env":
        posicion = 1
        while "=" in comando[posicion]:
            clave, valor = comando[posicion].split("=", 1)
            variables[clave] = valor
            posicion += 1
    return variables, comando[posicion], posicion + 1


def ejecutar_expdp(entorno: EntornoOracle, conexion: Conexion, parametros: list[str]) -> Salida:
    credenciales = f"{conexion.usuario}/{conexion.password}@{conexion.servicio}"
    # expdp rechaza «AS SYSDBA» sin comillas en el parfile (LRM-00112).
    userid = f'USERID="{credenciales} AS SYSDBA"' if conexion.sysdba else f"USERID={credenciales}"
    contenido = "\n".join([userid, *parametros]) + "\n"
    return entorno.ejecutar_herramienta(
        "expdp", lambda ruta: [f"PARFILE={ruta}"], contenido, prefijo="expdp", extension=".par"
    )
