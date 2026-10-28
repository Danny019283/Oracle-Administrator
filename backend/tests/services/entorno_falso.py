from pathlib import PurePosixPath

from src.services.entorno_oracle import EntornoOracle, Salida

RUTA_TEMPORAL = "/tmp/herramienta.tmp"


class EntornoFalso(EntornoOracle):
    """Registra lo que los servicios piden al entorno, sin ejecutar nada."""

    tipo_ruta = PurePosixPath

    def __init__(self, codigo=0, texto="", log=""):
        self.codigo = codigo
        self.texto = texto
        self.log = log
        self.herramientas = []
        self.lecturas = []
        self.carpetas = []

    def crear_carpeta(self, ruta):
        self.carpetas.append(ruta)

    def leer_archivo(self, ruta):
        self.lecturas.append(ruta)
        return self.log

    def ejecutar_herramienta(
        self, nombre, args, script, *, prefijo, extension="", variables=None
    ):
        self.herramientas.append(
            {
                "nombre": nombre,
                "args": args(RUTA_TEMPORAL),
                "script": script,
                "prefijo": prefijo,
                "extension": extension,
                "variables": variables,
            }
        )
        return Salida(codigo=self.codigo, texto=self.texto)
