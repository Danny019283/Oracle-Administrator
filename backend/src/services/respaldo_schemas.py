from datetime import datetime

from src.services.dumpfile import construir_nombres
from src.services.expdp_runner import Conexion, Ejecutor, ejecutar_expdp
from src.services.respaldo_tablas import RespaldoFallido, ResultadoRespaldo

__all__ = ["RespaldoFallido", "ResultadoRespaldo", "respaldar_schemas"]


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
