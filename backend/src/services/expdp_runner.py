import os
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class Conexion:
    usuario: str
    password: str
    servicio: str
    host: str = field(default_factory=lambda: os.environ.get("ORACLE_HOST", "localhost"))
    puerto: int = field(default_factory=lambda: int(os.environ.get("ORACLE_PORT", "1521")))
    sysdba: bool = False


@dataclass(frozen=True)
class Salida:
    codigo: int
    texto: str


Ejecutor = Callable[..., Salida]


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
    ruta = f"/tmp/{prefijo}_{uuid4().hex}{extension}"
    docker = ["docker", "exec", contenedor]

    ejecutar(
        ["docker", "exec", "-i", contenedor, "sh", "-c", f"umask 077; cat > {ruta}"],
        entrada=contenido,
    )
    try:
        return ejecutar([*docker, *comando(ruta)])
    finally:
        ejecutar([*docker, "rm", "-f", ruta])


def ejecutar_expdp(
    contenedor: str,
    conexion: Conexion,
    parametros: list[str],
    ejecutar: Ejecutor,
) -> Salida:
    credenciales = f"{conexion.usuario}/{conexion.password}@{conexion.servicio}"
    # expdp rechaza «AS SYSDBA» sin comillas en el parfile (LRM-00112).
    userid = f'USERID="{credenciales} AS SYSDBA"' if conexion.sysdba else f"USERID={credenciales}"
    contenido = "\n".join([userid, *parametros]) + "\n"
    return ejecutar_con_archivo(
        contenedor, "expdp", contenido,
        lambda ruta: ["expdp", f"PARFILE={ruta}"], ejecutar, extension=".par",
    )
