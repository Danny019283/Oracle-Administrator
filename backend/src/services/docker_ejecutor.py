from src.services.entorno_oracle import Salida
from src.services.procesos import ejecutar_proceso


def ejecutar_docker(args: list[str], entrada: str | None = None) -> Salida:
    return ejecutar_proceso(args, entrada)
