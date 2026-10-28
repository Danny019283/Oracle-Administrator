import os
import subprocess
from collections.abc import Mapping

from src.services.entorno_oracle import HerramientaNoDisponible, Salida


def ejecutar_proceso(
    args: list[str], entrada: str | None = None, variables: Mapping[str, str] | None = None
) -> Salida:
    entorno = {**os.environ, **variables} if variables else None
    try:
        resultado = subprocess.run(args, input=entrada, capture_output=True, text=True, env=entorno)
    except (FileNotFoundError, PermissionError):
        raise HerramientaNoDisponible(args[0]) from None
    return Salida(
        codigo=resultado.returncode,
        texto=(resultado.stdout + resultado.stderr).strip(),
    )
