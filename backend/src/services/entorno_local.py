from collections.abc import Callable, Mapping
from pathlib import Path, PurePath

from src.services.entorno_oracle import EntornoOracle, Salida


class SistemaLinux:
    """Implementador del Bridge: lo que depende del SO donde corre Oracle (Linux)."""

    tipo_ruta = Path

    def leer_archivo(self, ruta: PurePath) -> str:
        return Path(ruta).read_text()

    def crear_carpeta(self, ruta: PurePath) -> None:
        Path(ruta).mkdir(parents=True, exist_ok=True)


class EntornoLocal(EntornoOracle):
    """Estrategia: las herramientas corren en la misma máquina que el backend."""

    def __init__(self, sistema: SistemaLinux):
        self._sistema = sistema
        self.tipo_ruta = sistema.tipo_ruta

    def crear_carpeta(self, ruta: PurePath) -> None:
        self._sistema.crear_carpeta(ruta)

    def leer_archivo(self, ruta: PurePath) -> str:
        return self._sistema.leer_archivo(ruta)

    def ejecutar_herramienta(
        self,
        nombre: str,
        args: Callable[[str], list[str]],
        script: str,
        *,
        prefijo: str,
        extension: str = "",
        variables: Mapping[str, str] | None = None,
    ) -> Salida:
        raise NotImplementedError  # check 8
