from collections.abc import Collection
from datetime import datetime

from src.services.expdp_runner import Conexion, Ejecutor
from src.services.respaldo import (
    TABLAS,
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
    "respaldar_tablas",
    "validar_solicitud",
]


def validar_solicitud(
    tablas: list[str],
    directorio: str,
    nombre: str,
    tablas_disponibles: Collection[str],
    directorios_disponibles: Collection[str],
) -> None:
    validar_objetos(TABLAS, tablas, directorio, nombre, tablas_disponibles, directorios_disponibles)


def respaldar_tablas(
    conexion: Conexion,
    tablas: list[str],
    directorio: str,
    nombre: str,
    contenedor: str,
    ejecutar: Ejecutor,
    ahora: datetime,
    ruta_directorio: str | None = None,
) -> ResultadoRespaldo:
    return respaldar(
        TABLAS, conexion, tablas, directorio, nombre, contenedor, ejecutar, ahora, ruta_directorio
    )
