from datetime import datetime


def nombre_log_recuperacion(base: str, ahora: datetime) -> str:
    # El guion de la hora evita que `agrupar_archivos` lo tome por un archivo del respaldo (`_AAAAMMDD_HHMMSS`).
    return f"{base}_recuperacion_{ahora:%Y%m%d-%H%M%S}.log"
