import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePath, PureWindowsPath
from uuid import uuid4

from src.services.entorno_oracle import (
    ArchivoNoLegible,
    ComandoHerramienta,
    EntornoOracle,
    OperacionEntornoFallida,
    Salida,
)
from src.services.procesos import ejecutar_proceso


class SistemaLinux:
    """Implementador del Bridge: lo que depende del SO donde corre Oracle (Linux)."""

    tipo_ruta = Path

    def leer_archivo(self, ruta: PurePath) -> str:
        return Path(ruta).read_text(errors="replace")

    def crear_carpeta(self, ruta: PurePath) -> None:
        Path(ruta).mkdir(parents=True, exist_ok=True)

    def escribir_privado(self, ruta: PurePath, texto: str) -> None:
        # O_EXCL y 0600: nadie más puede crear ni leer el script (lleva credenciales)
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as archivo:
            archivo.write(texto)

    def borrar(self, ruta: PurePath) -> None:
        Path(ruta).unlink(missing_ok=True)

    def dar_permisos_a_oracle(self, ruta: PurePath, sid: str, ejecutar: Callable[..., Salida]) -> None:
        pass


class SistemaWindows:
    """Implementador del Bridge para Windows; `a_path` convierte la ruta en un Path real (se cambia en las pruebas)."""

    tipo_ruta = PureWindowsPath

    def __init__(self, a_path: Callable[[PurePath], Path] = Path):
        self._a_path = a_path

    def leer_archivo(self, ruta: PurePath) -> str:
        return self._a_path(ruta).read_text(errors="replace")

    def crear_carpeta(self, ruta: PurePath) -> None:
        self._a_path(ruta).mkdir(parents=True, exist_ok=True)

    def escribir_privado(self, ruta: PurePath, texto: str) -> None:
        # sin chmod: el temporal del perfil hereda la ACL privada del usuario
        self._a_path(ruta).write_text(texto)

    def borrar(self, ruta: PurePath) -> None:
        self._a_path(ruta).unlink(missing_ok=True)

    def dar_permisos_a_oracle(self, ruta: PurePath, sid: str, ejecutar: Callable[..., Salida]) -> None:
        servicio = f"OracleService{sid}"
        salida = ejecutar(["sc", "qc", servicio])
        if salida.codigo != 0:
            raise OperacionEntornoFallida(f"Falló «sc qc {servicio}»: {salida.texto}")
        coincidencia = re.search(r"SERVICE_START_NAME\s*:\s*(\S.*?)\s*$", salida.texto, re.MULTILINE)
        if not coincidencia:
            raise OperacionEntornoFallida(
                f"No se pudo leer SERVICE_START_NAME de la salida de «sc qc {servicio}»: {salida.texto}"
            )
        cuenta = "SYSTEM" if coincidencia[1] == "LocalSystem" else coincidencia[1]
        salida = ejecutar(["icacls", str(ruta), "/grant", f"{cuenta}:(OI)(CI)M"])
        if salida.codigo != 0:
            raise OperacionEntornoFallida(f"Falló «icacls {ruta}»: {salida.texto}")


class EntornoLocal(EntornoOracle):
    """Estrategia: las herramientas corren en la misma máquina que el backend."""

    def __init__(
        self, sistema: SistemaLinux | SistemaWindows, ejecutar: Callable[..., Salida] = ejecutar_proceso
    ):
        self._sistema = sistema
        self._ejecutar = ejecutar
        self.tipo_ruta = sistema.tipo_ruta

    def crear_carpeta(self, ruta: PurePath) -> None:
        self._sistema.crear_carpeta(ruta)

    def dar_permisos_a_oracle(self, ruta: PurePath, sid: str) -> None:
        self._sistema.dar_permisos_a_oracle(ruta, sid, self._ejecutar)

    def leer_archivo(self, ruta: PurePath) -> str:
        try:
            return self._sistema.leer_archivo(ruta)
        except OSError as error:
            raise ArchivoNoLegible(str(error)) from error

    def ejecutar(self, comando: ComandoHerramienta) -> Salida:
        ruta = self.tipo_ruta(tempfile.gettempdir()) / f"{comando.prefijo}_{uuid4().hex}{comando.extension}"
        try:
            self._sistema.escribir_privado(ruta, comando.script)
            return self._ejecutar([comando.nombre, *comando.args(str(ruta))], variables=comando.variables)
        finally:
            self._sistema.borrar(ruta)
