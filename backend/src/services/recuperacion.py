import re
from dataclasses import dataclass
from datetime import datetime

from src.services.archivos_respaldo import RespaldoInvalido, resolver_respaldo
from src.services.directorios import Consulta
from src.services.entorno_oracle import ArchivoNoLegible, EntornoOracle
from src.services.errores_oracle import explicar_error
from src.services.expdp_runner import Conexion, ejecutar_impdp
from src.services.identificadores import normalizar_identificador

_EXISTENTES = ("SKIP", "APPEND", "TRUNCATE", "REPLACE")


def _tabla_con_owner(valor: str) -> str:
    partes = (valor or "").split(".")
    if len(partes) != 2:
        raise RespaldoInvalido(f"La tabla '{valor}' debe tener el formato OWNER.TABLA")
    return f"{normalizar_identificador(partes[0], 'el owner')}.{normalizar_identificador(partes[1], 'la tabla')}"


def validar_solicitud_datapump(objeto_modo: str, objetos: list[str], existentes: str = "SKIP") -> tuple[list[str], str]:
    """Devuelve (objetos normalizados, acción sobre tablas existentes) o lanza RespaldoInvalido/IdentificadorInvalido."""
    if objeto_modo not in ("tablas", "schemas"):
        raise RespaldoInvalido("El modo debe ser Tablas o Schemas")
    if not objetos:
        raise RespaldoInvalido("Debes indicar al menos un objeto para recuperar")
    if existentes not in _EXISTENTES:
        raise RespaldoInvalido("La acción sobre tablas existentes debe ser SKIP, APPEND, TRUNCATE o REPLACE")
    if objeto_modo == "tablas":
        return [_tabla_con_owner(o) for o in objetos], existentes
    return [normalizar_identificador(o, "el schema") for o in objetos], existentes


_HASTA = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def validar_hasta(texto: str, fecha_respaldo: datetime, ahora: datetime) -> str:
    """Devuelve la fecha como DD/MM/YYYY HH24:MI:SS (la que va en TO_DATE) o lanza RespaldoInvalido."""
    try:
        if not _HASTA.fullmatch(texto or ""):
            raise ValueError
        fecha = datetime.strptime(texto, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise RespaldoInvalido("La fecha límite debe tener el formato AAAA-MM-DD HH:MM:SS") from None
    if fecha > ahora:
        raise RespaldoInvalido("La fecha límite no puede ser futura")
    if fecha < fecha_respaldo:
        raise RespaldoInvalido("La fecha límite no puede ser anterior a la fecha del respaldo")
    return fecha.strftime("%d/%m/%Y %H:%M:%S")


def validar_remap(tabla: str, nuevo_nombre: str) -> tuple[str, str]:
    """Devuelve (OWNER.TABLA, NUEVO) normalizados o lanza RespaldoInvalido/IdentificadorInvalido."""
    tabla = _tabla_con_owner(tabla)
    nuevo = normalizar_identificador(nuevo_nombre, "la tabla nueva")
    if nuevo == tabla.split(".")[1]:
        raise RespaldoInvalido("El nombre nuevo debe ser distinto del de la tabla original")
    return tabla, nuevo


def nombre_log_recuperacion(base: str, ahora: datetime) -> str:
    # El guion de la hora evita que `agrupar_archivos` lo tome por un archivo del respaldo (`_AAAAMMDD_HHMMSS`).
    return f"{base}_recuperacion_{ahora:%Y%m%d-%H%M%S}.log"


class RecuperacionFallida(Exception):
    def __init__(self, codigo: int, log: str, herramienta: str = "impdp"):
        super().__init__(f"La recuperación falló: {herramienta} terminó con código {codigo}")
        self.codigo = codigo
        self.log = log
        self.explicacion = explicar_error(log)


@dataclass(frozen=True)
class ResultadoRecuperacion:
    log: str
    advertencia: str | None = None


def recuperar_datapump(
    consulta: Consulta,
    entorno: EntornoOracle,
    conexion: Conexion,
    directorio: str,
    base: str,
    objeto_modo: str,
    objetos: list[str],
    existentes: str,
    ahora: datetime,
) -> ResultadoRecuperacion:
    carpeta, respaldo = resolver_respaldo(consulta, entorno, directorio, base)
    if respaldo.tipo != "Data Pump":
        raise RespaldoInvalido("Solo se puede recuperar con Data Pump un respaldo de tipo Data Pump")
    objetos, existentes = validar_solicitud_datapump(objeto_modo, objetos, existentes)
    nombre_log = nombre_log_recuperacion(base, ahora)
    salida = ejecutar_impdp(
        entorno,
        conexion,
        [
            f"DIRECTORY={respaldo.directorio}",
            f"DUMPFILE={base}.dmp",
            f"LOGFILE={nombre_log}",
            f"{'TABLES' if objeto_modo == 'tablas' else 'SCHEMAS'}={','.join(objetos)}",
            f"TABLE_EXISTS_ACTION={existentes}",
        ],
    )
    try:
        log = entorno.leer_archivo(carpeta / nombre_log)
    except ArchivoNoLegible:
        log = salida.texto
    if salida.codigo != 0:
        raise RecuperacionFallida(salida.codigo, log)
    advertencia = None if respaldo.estado == "Completo" else f"El respaldo tiene estado «{respaldo.estado}»"
    return ResultadoRecuperacion(log, advertencia)
