from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from src.services.directorios import Directorio
from src.services.errores_oracle import explicar_error
from src.services.expdp_runner import Ejecutor
from src.services.respaldo import RespaldoFallido, SolicitudInvalida, errores_destino
from src.services.rman_runner import ejecutar_rman

Consulta = Callable[..., Sequence[Sequence[Any]]]

_SCRIPT_LIMPIEZA = """CROSSCHECK BACKUP;
CROSSCHECK ARCHIVELOG ALL;
DELETE NOPROMPT OBSOLETE REDUNDANCY 1;
"""


class SinArchivelog(Exception):
    def __init__(self):
        super().__init__(
            "La base de datos no está en ARCHIVELOG: actívalo para poder respaldar"
        )


@dataclass(frozen=True)
class AdvertenciaLimpieza:
    explicacion: str
    log: str


@dataclass(frozen=True)
class ResultadoFull:
    log: str
    advertencia: AdvertenciaLimpieza | None = None


def en_archivelog(consulta: Consulta) -> bool:
    filas = consulta("SELECT log_mode FROM v$database")
    return bool(filas) and filas[0][0] == "ARCHIVELOG"


def _script_respaldo(ruta_directorio: str, nombre: str) -> str:
    return f"""RUN {{
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  BACKUP INCREMENTAL LEVEL 0
  DATABASE
  TAG 'MANUAL_FULL_L0'
  FORMAT '{ruta_directorio}/{nombre}_%d_%T_%s_%p';
  RELEASE CHANNEL ch1;
}}
"""


def respaldar_full(
    consulta: Consulta,
    directorios: Sequence[Directorio],
    directorio: str,
    nombre: str,
    contenedor: str,
    ejecutar: Ejecutor,
) -> ResultadoFull:
    errores = errores_destino(directorio, nombre, [d.nombre for d in directorios])
    if errores:
        raise SolicitudInvalida(errores)
    if not en_archivelog(consulta):
        raise SinArchivelog()

    ruta = next(d.ruta for d in directorios if d.nombre == directorio)
    respaldo = ejecutar_rman(contenedor, _script_respaldo(ruta, nombre), ejecutar)
    if respaldo.codigo != 0:
        raise RespaldoFallido(respaldo.codigo, respaldo.texto, "rman")

    limpieza = ejecutar_rman(contenedor, _SCRIPT_LIMPIEZA, ejecutar)
    advertencia = None
    if limpieza.codigo != 0:
        advertencia = AdvertenciaLimpieza(explicar_error(limpieza.texto), limpieza.texto)
    return ResultadoFull(log=respaldo.texto, advertencia=advertencia)
