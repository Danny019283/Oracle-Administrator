from pathlib import PurePosixPath

from src.services.entorno_oracle import ArchivoNoLegible, EntornoOracle, Salida

RUTA_TEMPORAL = "/tmp/herramienta.tmp"


class EntornoFalso(EntornoOracle):
    """Registra lo que los servicios piden al entorno, sin ejecutar nada."""

    tipo_ruta = PurePosixPath

    def __init__(self, codigo=0, texto="", log="", salidas=None):
        self.codigo = codigo
        self.texto = texto
        self.log = log
        # salidas: una por ejecución de herramienta, en orden; sin ella se repite codigo/texto
        self.salidas = list(salidas) if salidas else None
        self.herramientas = []
        self.lecturas = []
        self.carpetas = []

    def crear_carpeta(self, ruta):
        self.carpetas.append(ruta)

    def leer_archivo(self, ruta):
        self.lecturas.append(ruta)
        # log=None simula un log que el entorno no puede leer
        if self.log is None:
            raise ArchivoNoLegible(str(ruta))
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
        if self.salidas:
            return self.salidas[len(self.herramientas) - 1]
        return Salida(codigo=self.codigo, texto=self.texto)
