import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path, PurePath
from uuid import uuid4

from src.services.entorno_oracle import EntornoOracle, Salida
from src.services.procesos import ejecutar_proceso


class SistemaLinux:
    """Implementador del Bridge: lo que depende del SO donde corre Oracle (Linux)."""

    tipo_ruta = Path

    def leer_archivo(self, ruta: PurePath) -> str:
        return Path(ruta).read_text()

    def crear_carpeta(self, ruta: PurePath) -> None:
        Path(ruta).mkdir(parents=True, exist_ok=True)


class EntornoLocal(EntornoOracle):
    """Estrategia: las herramientas corren en la misma máquina que el backend."""

    def __init__(self, sistema: SistemaLinux, ejecutar: Callable[..., Salida] = ejecutar_proceso):
        self._sistema = sistema
        self._ejecutar = ejecutar
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
        ruta = Path(tempfile.gettempdir()) / f"{prefijo}_{uuid4().hex}{extension}"
        # O_EXCL y 0600: nadie más puede crear ni leer el script (lleva credenciales)
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w") as archivo:
                archivo.write(script)
            return self._ejecutar([nombre, *args(str(ruta))], variables=variables)
        finally:
            ruta.unlink(missing_ok=True)
