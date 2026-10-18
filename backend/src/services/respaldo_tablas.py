from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from src.services.dumpfile import NombreInvalido, construir_nombres
from src.services.expdp_runner import Conexion, Ejecutor, ejecutar_expdp


@dataclass(frozen=True)
class ResultadoRespaldo:
    dmp: str
    log: str


class SolicitudInvalida(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


def validar_solicitud(
    tablas: list[str],
    directorio: str,
    nombre: str,
    tablas_disponibles: Collection[str],
    directorios_disponibles: Collection[str],
) -> None:
    errores = []

    if not tablas:
        errores.append("Debes seleccionar al menos una tabla")
    for tabla in tablas:
        if tabla not in tablas_disponibles:
            errores.append(f"La tabla {tabla} no pertenece al schema del usuario")

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


def respaldar_tablas(
    conexion: Conexion,
    tablas: list[str],
    directorio: str,
    nombre: str,
    contenedor: str,
    ejecutar: Ejecutor,
    ahora: datetime,
) -> ResultadoRespaldo:
    nombres = construir_nombres(nombre, ahora)
    ejecutar_expdp(
        contenedor,
        conexion,
        [
            f"TABLES={','.join(tablas)}",
            f"DIRECTORY={directorio}",
            f"DUMPFILE={nombres.dmp}",
            f"LOGFILE={nombres.log}",
        ],
        ejecutar,
    )
    return ResultadoRespaldo(dmp=nombres.dmp, log=nombres.log)
