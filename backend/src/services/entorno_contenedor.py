from collections.abc import Callable, Mapping
from pathlib import PurePath, PurePosixPath
from uuid import uuid4

from src.services.entorno_oracle import (
    ArchivoNoLegible,
    EntornoOracle,
    HerramientaNoDisponible,
    OperacionEntornoFallida,
    Salida,
)

Ejecutor = Callable[..., Salida]


class EntornoContenedor(EntornoOracle):
    """Estrategia: las herramientas corren dentro de un contenedor (`<cli> exec`, con docker o podman)."""

    tipo_ruta = PurePosixPath

    def __init__(self, contenedor: str, ejecutar: Ejecutor, cli: str = "docker"):
        self._cli = cli
        self._contenedor = contenedor
        self._ejecutar = ejecutar

    def crear_carpeta(self, ruta: PurePath) -> None:
        salida = self._ejecutar([self._cli, "exec", self._contenedor, "mkdir", "-p", str(ruta)])
        if salida.codigo != 0:
            raise OperacionEntornoFallida(salida.texto)

    def leer_archivo(self, ruta: PurePath) -> str:
        salida = self._ejecutar([self._cli, "exec", self._contenedor, "cat", str(ruta)])
        if salida.codigo != 0:
            raise ArchivoNoLegible(salida.texto)
        return salida.texto

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
        docker = [self._cli, "exec", self._contenedor]
        entorno = [f"{clave}={valor}" for clave, valor in (variables or {}).items()]
        prefijo_env = ["env", *entorno] if entorno else []

        self._ejecutar(
            [self._cli, "exec", "-i", self._contenedor, "sh", "-c", f"umask 077; cat > {ruta}"],
            entrada=script,
        )
        try:
            salida = self._ejecutar([*docker, *prefijo_env, nombre, *args(ruta)])
            # 127 de exec: la herramienta no existe dentro del contenedor
            if salida.codigo == 127:
                raise HerramientaNoDisponible(nombre)
            return salida
        finally:
            self._ejecutar([*docker, "rm", "-f", ruta])
