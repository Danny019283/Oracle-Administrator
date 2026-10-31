from collections.abc import Callable
from pathlib import PurePath, PurePosixPath
from uuid import uuid4

from src.services.entorno_oracle import (
    ArchivoEntorno,
    ArchivoNoLegible,
    ComandoHerramienta,
    EntornoOracle,
    HerramientaNoDisponible,
    OperacionEntornoFallida,
    Salida,
)

Ejecutor = Callable[..., Salida]


class EntornoContenedor(EntornoOracle):
    """Estrategia: las herramientas corren dentro de un contenedor (`<cli> exec`, con docker o podman)."""

    tipo_ruta = PurePosixPath

    def __init__(
        self, contenedor: str, ejecutar: Ejecutor, cli: str = "docker", usuario_oracle: str = "oracle:oinstall"
    ):
        self._cli = cli
        self._usuario_oracle = usuario_oracle
        self._contenedor = contenedor
        self._ejecutar = ejecutar

    def crear_carpeta(self, ruta: PurePath) -> None:
        salida = self._ejecutar([self._cli, "exec", self._contenedor, "mkdir", "-p", str(ruta)])
        if salida.codigo != 0:
            raise OperacionEntornoFallida(salida.texto)

    def dar_permisos_a_oracle(self, ruta: PurePath, sid: str) -> None:
        # sid se ignora: el contenedor tiene un solo usuario de Oracle
        for comando in (["chown", self._usuario_oracle], ["chmod", "u+rwx"]):
            salida = self._ejecutar([self._cli, "exec", "-u", "root", self._contenedor, *comando, str(ruta)])
            if salida.codigo != 0:
                raise OperacionEntornoFallida(salida.texto)

    def leer_archivo(self, ruta: PurePath) -> str:
        salida = self._ejecutar([self._cli, "exec", self._contenedor, "cat", str(ruta)])
        if salida.codigo != 0:
            raise ArchivoNoLegible(salida.texto)
        return salida.texto

    def listar_archivos(self, ruta: PurePath) -> list[ArchivoEntorno]:
        formato = "%f\\t%s\\t%T@\\n"
        salida = self._ejecutar(
            [self._cli, "exec", self._contenedor, "find", str(ruta), "-maxdepth", "1", "-type", "f", "-printf", formato]
        )
        if salida.codigo != 0:
            raise OperacionEntornoFallida(salida.texto)
        archivos = []
        for linea in salida.texto.splitlines():
            if linea:
                nombre, tamano, modificado = linea.rsplit("\t", 2)
                archivos.append(ArchivoEntorno(nombre, int(tamano), float(modificado)))
        return archivos

    def borrar_archivo(self, ruta: PurePath) -> None:
        salida = self._ejecutar([self._cli, "exec", self._contenedor, "rm", "-f", str(ruta)])
        if salida.codigo != 0:
            raise OperacionEntornoFallida(salida.texto)

    def ejecutar(self, comando: ComandoHerramienta) -> Salida:
        ruta = f"/tmp/{comando.prefijo}_{uuid4().hex}{comando.extension}"
        docker = [self._cli, "exec", self._contenedor]
        entorno = [f"{clave}={valor}" for clave, valor in (comando.variables or {}).items()]
        prefijo_env = ["env", *entorno] if entorno else []

        self._ejecutar(
            [self._cli, "exec", "-i", self._contenedor, "sh", "-c", f"umask 077; cat > {ruta}"],
            entrada=comando.script,
        )
        try:
            salida = self._ejecutar([*docker, *prefijo_env, comando.nombre, *comando.args(ruta)])
            # 127 de exec: la herramienta no existe dentro del contenedor
            if salida.codigo == 127:
                raise HerramientaNoDisponible(comando.nombre)
            return salida
        finally:
            self._ejecutar([*docker, "rm", "-f", ruta])
