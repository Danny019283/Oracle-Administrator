import subprocess

from src.services.expdp_runner import Salida


def ejecutar_docker(args: list[str], entrada: str | None = None) -> Salida:
    resultado = subprocess.run(args, input=entrada, capture_output=True, text=True)
    return Salida(
        codigo=resultado.returncode,
        texto=(resultado.stdout + resultado.stderr).strip(),
    )
