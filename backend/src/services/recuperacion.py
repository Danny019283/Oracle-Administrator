from datetime import datetime

from src.services.archivos_respaldo import RespaldoInvalido
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


def nombre_log_recuperacion(base: str, ahora: datetime) -> str:
    # El guion de la hora evita que `agrupar_archivos` lo tome por un archivo del respaldo (`_AAAAMMDD_HHMMSS`).
    return f"{base}_recuperacion_{ahora:%Y%m%d-%H%M%S}.log"
