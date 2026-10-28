from collections.abc import Mapping

from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_local import EntornoLocal, SistemaLinux, SistemaWindows
from src.services.entorno_oracle import EntornoOracle
from src.services.procesos import ejecutar_proceso

ENTORNOS = ("contenedor", "local")
CLIS = ("docker", "podman")


class ConfiguracionInvalida(Exception):
    """Una variable de entorno tiene un valor no admitido; el mensaje indica los válidos."""


def _elegir(variables: Mapping[str, str], nombre: str, validos: tuple[str, ...]) -> str:
    valor = variables.get(nombre, validos[0])
    if valor not in validos:
        raise ConfiguracionInvalida(
            f"{nombre}={valor!r} no es válido; los valores admitidos son: {', '.join(validos)}."
        )
    return valor


def fabrica_desde_variables(variables: Mapping[str, str], plataforma: str) -> EntornoOracle:
    """Abstract Factory: crea la estrategia y su implementador según las variables y `sys.platform`."""
    entorno = _elegir(variables, "ORACLE_ENTORNO", ENTORNOS)
    if entorno == "local":
        return EntornoLocal(SistemaWindows() if plataforma.startswith("win") else SistemaLinux())
    cli = _elegir(variables, "ORACLE_CONTAINER_CLI", CLIS)
    return EntornoContenedor(variables.get("ORACLE_CONTAINER", "oracle21c"), ejecutar_proceso, cli)
