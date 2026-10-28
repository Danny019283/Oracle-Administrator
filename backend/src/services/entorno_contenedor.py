from collections.abc import Callable, Mapping
from pathlib import PurePath, PurePosixPath
from uuid import uuid4

from src.services.entorno_oracle import EntornoOracle, Salida

Ejecutor = Callable[..., Salida]


class EntornoContenedor(EntornoOracle):
    """Estrategia: las herramientas corren dentro de un contenedor (`docker exec`)."""

    tipo_ruta = PurePosixPath

    def __init__(self, contenedor: str, ejecutar: Ejecutor):
        self._contenedor = contenedor
        self._ejecutar = ejecutar

    def leer_archivo(self, ruta: PurePath) -> str:
        return self._ejecutar(["docker", "exec", self._contenedor, "cat", str(ruta)]).texto

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
        ruta = f"/tmp/{prefijo}_{uuid4().hex}{extension}"
        docker = ["docker", "exec", self._contenedor]
        entorno = [f"{clave}={valor}" for clave, valor in (variables or {}).items()]
        prefijo_env = ["env", *entorno] if entorno else []

        self._ejecutar(
            ["docker", "exec", "-i", self._contenedor, "sh", "-c", f"umask 077; cat > {ruta}"],
            entrada=script,
        )
        try:
            return self._ejecutar([*docker, *prefijo_env, nombre, *args(ruta)])
        finally:
            self._ejecutar([*docker, "rm", "-f", ruta])
