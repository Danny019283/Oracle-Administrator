from collections.abc import Collection
from datetime import datetime

from src.services.dumpfile import NombreInvalido, construir_nombres
from src.services.expdp_runner import Conexion, Ejecutor, ejecutar_expdp
from src.services.respaldo_tablas import (
    RespaldoFallido,
    ResultadoRespaldo,
    SolicitudInvalida,
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
    errores = []

    if not schemas:
        errores.append("Debes seleccionar al menos un schema")
    for schema in schemas:
        if schema not in schemas_disponibles:
            errores.append(f"El schema {schema} no es un schema de usuario disponible")

    if not directorio:
        errores.append("Debes elegir un directorio")
    elif directorio not in directorios_disponibles:
        errores.append(f"El directorio {directorio} no está disponible")

    if not nombre:
        errores.append("Debes ingresar un nombre de dumpfile")
    else:
        try:
            construir_nombres(nombre, datetime.now())
        except NombreInvalido as error:
            errores.append(str(error))

    if errores:
        raise SolicitudInvalida(errores)


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
    nombres = construir_nombres(nombre, ahora)
    salida = ejecutar_expdp(
        contenedor,
        conexion,
        [
            f"SCHEMAS={','.join(schemas)}",
            f"DIRECTORY={directorio}",
            f"DUMPFILE={nombres.dmp}",
            f"LOGFILE={nombres.log}",
        ],
        ejecutar,
    )
    if salida.codigo != 0:
        log = salida.texto
        if ruta_directorio is not None:
            log = ejecutar(
                ["docker", "exec", contenedor, "cat", f"{ruta_directorio}/{nombres.log}"]
            ).texto
        raise RespaldoFallido(salida.codigo, log)
    return ResultadoRespaldo(dmp=nombres.dmp, log=nombres.log)
