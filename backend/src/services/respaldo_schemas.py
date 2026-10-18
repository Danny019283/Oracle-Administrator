from collections.abc import Collection
from datetime import datetime

from src.services.expdp_runner import Conexion, Ejecutor
from src.services.respaldo import (
    SCHEMAS,
    RespaldoFallido,
    ResultadoRespaldo,
    SolicitudInvalida,
    respaldar,
    validar_solicitud as validar_objetos,
)

__all__ = [
    "RespaldoFallido",
    "ResultadoRespaldo",
    "SolicitudInvalida",
    "respaldar_schemas",
    "validar_solicitud_schemas",
]


def validar_solicitud_schemas(
    schemas: list[str],
    directorio: str,
    nombre: str,
    schemas_disponibles: Collection[str],
    directorios_disponibles: Collection[str],
) -> None:
    validar_objetos(SCHEMAS, schemas, directorio, nombre, schemas_disponibles, directorios_disponibles)


def respaldar_schemas(
    conexion: Conexion,
    schemas: list[str],
    directorio: str,
    nombre: str,
    contenedor: str,
    ejecutar: Ejecutor,
    ahora: datetime,
    ruta_directorio: str | None = None,
) -> ResultadoRespaldo:
    return respaldar(
        SCHEMAS, conexion, schemas, directorio, nombre, contenedor, ejecutar, ahora, ruta_directorio
    )
