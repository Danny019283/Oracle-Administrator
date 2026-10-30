import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePath, PureWindowsPath
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
from src.services.procesos import ejecutar_proceso


def _listar(carpeta: Path) -> list[ArchivoEntorno]:
    return [
        ArchivoEntorno(entrada.name, (datos := entrada.stat()).st_size, datos.st_mtime)
        for entrada in carpeta.iterdir()
        if entrada.is_file()
    ]


class SistemaLinux:
    """Implementador del Bridge: lo que depende del SO donde corre Oracle (Linux)."""

    tipo_ruta = Path

    def leer_archivo(self, ruta: PurePath) -> str:
        return Path(ruta).read_text(errors="replace")

    def listar_archivos(self, ruta: PurePath) -> list[ArchivoEntorno]:
        return _listar(Path(ruta))

    def crear_carpeta(self, ruta: PurePath) -> None:
        Path(ruta).mkdir(parents=True, exist_ok=True)

    def escribir_privado(self, ruta: PurePath, texto: str) -> None:
        # O_EXCL y 0600: nadie más puede crear ni leer el script (lleva credenciales)
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as archivo:
            archivo.write(texto)

    def borrar(self, ruta: PurePath) -> None:
        Path(ruta).unlink(missing_ok=True)

    def borrar_carpeta(self, ruta: PurePath) -> None:
        shutil.rmtree(Path(ruta))

    def dar_permisos_a_oracle(self, ruta: PurePath, sid: str, ejecutar: Callable[..., Salida]) -> None:
        proceso = f"ora_pmon_{sid}"
        try:
            salida = ejecutar(["ps", "-C", proceso, "-o", "user="])
        except HerramientaNoDisponible as error:
            raise OperacionEntornoFallida(f"Falló «ps -C {proceso}»: {error}") from error
        if salida.codigo != 0:
            raise OperacionEntornoFallida(f"Falló «ps -C {proceso}»: {salida.texto}")
        usuario = next((linea.strip() for linea in salida.texto.splitlines() if linea.strip()), "")
        if not usuario:
            raise OperacionEntornoFallida(
                f"«ps -C {proceso}» no devolvió ningún usuario: ¿la instancia {sid} está en marcha?"
            )
        # el usuario va a un argumento de setfacl: sin guion inicial ni caracteres raros
        if not re.fullmatch(r"[\w.][\w.-]*", usuario, re.ASCII):
            raise OperacionEntornoFallida(f"«ps -C {proceso}» devolvió un usuario no válido: {usuario!r}")
        try:
            salida = ejecutar(["setfacl", "-m", f"u:{usuario}:rwx", str(ruta)])
        except HerramientaNoDisponible as error:
            raise OperacionEntornoFallida(f"Falló «setfacl {ruta}»: {error} Instale el paquete acl.") from error
        if salida.codigo != 0:
            raise OperacionEntornoFallida(f"Falló «setfacl {ruta}»: {salida.texto}")


class SistemaWindows:
    """Implementador del Bridge para Windows; `a_path` convierte la ruta en un Path real (se cambia en las pruebas)."""

    tipo_ruta = PureWindowsPath

    def __init__(self, a_path: Callable[[PurePath], Path] = Path):
        self._a_path = a_path

    def leer_archivo(self, ruta: PurePath) -> str:
        return self._a_path(ruta).read_text(errors="replace")

    def listar_archivos(self, ruta: PurePath) -> list[ArchivoEntorno]:
        return _listar(self._a_path(ruta))

    def crear_carpeta(self, ruta: PurePath) -> None:
        self._a_path(ruta).mkdir(parents=True, exist_ok=True)

    def escribir_privado(self, ruta: PurePath, texto: str) -> None:
        # sin chmod: el temporal del perfil hereda la ACL privada del usuario
        self._a_path(ruta).write_text(texto)

    def borrar(self, ruta: PurePath) -> None:
        self._a_path(ruta).unlink(missing_ok=True)

    def borrar_carpeta(self, ruta: PurePath) -> None:
        shutil.rmtree(self._a_path(ruta))

    def dar_permisos_a_oracle(self, ruta: PurePath, sid: str, ejecutar: Callable[..., Salida]) -> None:
        clave = f"HKLM\\SYSTEM\\CurrentControlSet\\Services\\OracleService{sid}"
        salida = ejecutar(["reg", "query", clave, "/v", "ObjectName"])
        if salida.codigo != 0:
            raise OperacionEntornoFallida(f"Falló «reg query {clave}»: {salida.texto}")
        # solo el nombre del valor y el tipo, que no dependen del idioma
        coincidencia = re.search(r"^[ \t]*ObjectName[ \t]+REG_SZ[ \t]+(\S.*?)\s*$", salida.texto, re.MULTILINE)
        if not coincidencia:
            raise OperacionEntornoFallida(
                f"No se pudo leer la cuenta (ObjectName) de la salida de «reg query {clave}»: {salida.texto}"
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

    def listar_archivos(self, ruta: PurePath) -> list[ArchivoEntorno]:
        try:
            return self._sistema.listar_archivos(ruta)
        except OSError as error:
            raise OperacionEntornoFallida(str(error)) from error

    def borrar_archivo(self, ruta: PurePath) -> None:
        try:
            self._sistema.borrar(ruta)
        except OSError as error:
            raise OperacionEntornoFallida(str(error)) from error

    def borrar_carpeta(self, ruta: PurePath) -> None:
        try:
            self._sistema.borrar_carpeta(ruta)
        except OSError as error:
            raise OperacionEntornoFallida(str(error)) from error

    def ejecutar(self, comando: ComandoHerramienta) -> Salida:
        ruta = self.tipo_ruta(tempfile.gettempdir()) / f"{comando.prefijo}_{uuid4().hex}{comando.extension}"
        try:
            self._sistema.escribir_privado(ruta, comando.script)
            return self._ejecutar([comando.nombre, *comando.args(str(ruta))], variables=comando.variables)
        finally:
            self._sistema.borrar(ruta)
