from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.services.directorios import Directorio
from src.services.dumpfile import construir_base
from src.services.entorno_oracle import ArchivoNoLegible, EntornoOracle
from src.services.errores_oracle import explicar_error
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


def _script_respaldo(entorno: EntornoOracle, ruta_directorio: str, base: str) -> str:
    formato = entorno.tipo_ruta(ruta_directorio) / f"{base}_%d_%s_%p.dbf"
    return f"""RUN {{
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  BACKUP INCREMENTAL LEVEL 0
  DATABASE
  TAG 'MANUAL_FULL_L0'
  FORMAT '{formato}';
  RELEASE CHANNEL ch1;
}}
"""


def respaldar_full(
    consulta: Consulta,
    directorios: Sequence[Directorio],
    directorio: str,
    nombre: str,
    entorno: EntornoOracle,
    sid: str,
    ahora: datetime,
) -> ResultadoFull:
    errores = errores_destino(directorio, nombre, [d.nombre for d in directorios])
    if errores:
        raise SolicitudInvalida(errores)
    if not en_archivelog(consulta):
        raise SinArchivelog()

    ruta = next(d.ruta for d in directorios if d.nombre == directorio)
    base = construir_base(nombre, ahora)
    ruta_log = entorno.tipo_ruta(ruta) / f"{base}.log"
    respaldo = ejecutar_rman(entorno, _script_respaldo(entorno, ruta, base), sid, log=ruta_log)
    # con `log=` RMAN deja su salida en el archivo, no en stdout
    try:
        log = entorno.leer_archivo(ruta_log)
    except ArchivoNoLegible:
        log = respaldo.texto
    if respaldo.codigo != 0:
        raise RespaldoFallido(respaldo.codigo, log, "rman")

    limpieza = ejecutar_rman(entorno, _SCRIPT_LIMPIEZA, sid)
    advertencia = None
    if limpieza.codigo != 0:
        advertencia = AdvertenciaLimpieza(explicar_error(limpieza.texto), limpieza.texto)
    return ResultadoFull(log=log, advertencia=advertencia)
