from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class Salida:
    codigo: int
    texto: str


@dataclass(frozen=True)
class ComandoHerramienta:
    """Comando: una herramienta de Oracle lista para ejecutarse, con su script temporal."""

    nombre: str
    args: Callable[[str], list[str]]
    script: str
    prefijo: str
    extension: str = ""
    variables: Mapping[str, str] | None = None


class OperacionEntornoFallida(Exception):
    """Una operación del entorno terminó con error; el mensaje es la salida del comando."""


class ArchivoNoLegible(Exception):
    """El archivo no se pudo leer en el entorno; el mensaje es el detalle del fallo."""


class HerramientaNoDisponible(Exception):
    """El ejecutable no existe o no se pudo lanzar; el mensaje nombra la herramienta."""

    def __init__(self, herramienta: str):
        super().__init__(f"No se pudo ejecutar «{herramienta}»: no está disponible en el entorno.")
        self.herramienta = herramienta


class EntornoOracle(ABC):
    """Puerto: dónde corren las herramientas de Oracle (expdp, rman, sqlplus).
    Los servicios solo conocen esta interfaz, no el entorno concreto."""

    # Clase pathlib del SO del servidor de Oracle, para armar rutas sin conocer el entorno.
    tipo_ruta: type[PurePath]

    @abstractmethod
    def crear_carpeta(self, ruta: PurePath) -> None:
        """Crea la carpeta con sus padres; no falla si ya existe."""

    @abstractmethod
    def dar_permisos_a_oracle(self, ruta: PurePath) -> None:
        """Deja la carpeta (que debe existir) en manos del usuario de Oracle; nunca la crea."""

    @abstractmethod
    def leer_archivo(self, ruta: PurePath) -> str: ...

    @abstractmethod
    def ejecutar(self, comando: ComandoHerramienta) -> Salida:
        """Escribe `comando.script` en un temporal privado (sin que aparezca en los argumentos
        del proceso), ejecuta `comando.nombre` con `comando.args(ruta_del_temporal)` y siempre lo borra."""
