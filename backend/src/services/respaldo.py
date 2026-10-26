from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Any
from datetime import datetime

from src.services.dumpfile import NombreInvalido, construir_nombres
from src.services.errores_oracle import explicar_error
from src.services.expdp_runner import Conexion, Ejecutor, ejecutar_expdp


class SolicitudInvalida(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


Consulta = Callable[..., Sequence[Sequence[Any]]]


class SinObjetos(Exception):
    pass


def listar_objetos(
    consulta: Consulta, sql: str, mensaje: str, sin_objetos: type[SinObjetos]
) -> list[str]:
    filas = consulta(sql)
    if not filas:
        raise sin_objetos(mensaje)
    return [fila[0] for fila in filas]


def leer_log(contenedor: str, ruta: str, ejecutar: Ejecutor) -> str:
    return ejecutar(["docker", "exec", contenedor, "cat", ruta]).texto


class RespaldoFallido(Exception):
    def __init__(self, codigo: int, log: str, herramienta: str = "expdp"):
        super().__init__(f"El respaldo falló: {herramienta} terminó con código {codigo}")
        self.codigo = codigo
        self.log = log
        self.explicacion = explicar_error(log)


@dataclass(frozen=True)
class ResultadoRespaldo:
    dmp: str
    log: str


@dataclass(frozen=True)
class TipoObjeto:
    clave_expdp: str
    sin_seleccion: str
    fuera_de_lista: str


TABLAS = TipoObjeto(
    clave_expdp="TABLES",
    sin_seleccion="Debes seleccionar al menos una tabla",
    fuera_de_lista="La tabla {} no pertenece al schema del usuario",
)

SCHEMAS = TipoObjeto(
    clave_expdp="SCHEMAS",
    sin_seleccion="Debes seleccionar al menos un schema",
    fuera_de_lista="El schema {} no es un schema de usuario disponible",
)


def validar_solicitud(
    tipo: TipoObjeto,
    objetos: list[str],
    directorio: str,
    nombre: str,
    objetos_disponibles: Collection[str],
    directorios_disponibles: Collection[str],
) -> None:
    errores = []

    if not objetos:
        errores.append(tipo.sin_seleccion)
    for objeto in objetos:
        if objeto not in objetos_disponibles:
            errores.append(tipo.fuera_de_lista.format(objeto))

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


def respaldar(
    tipo: TipoObjeto,
    conexion: Conexion,
    objetos: list[str],
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
            f"{tipo.clave_expdp}={','.join(objetos)}",
            f"DIRECTORY={directorio}",
            f"DUMPFILE={nombres.dmp}",
            f"LOGFILE={nombres.log}",
        ],
        ejecutar,
    )
    if salida.codigo != 0:
        log = salida.texto
        if ruta_directorio is not None:
            log = leer_log(contenedor, f"{ruta_directorio}/{nombres.log}", ejecutar)
        raise RespaldoFallido(salida.codigo, log)
    return ResultadoRespaldo(dmp=nombres.dmp, log=nombres.log)
