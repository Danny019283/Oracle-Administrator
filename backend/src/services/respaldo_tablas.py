from collections.abc import Collection
from datetime import datetime

from src.services.dumpfile import NombreInvalido, construir_nombres


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
