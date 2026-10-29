from pathlib import PurePosixPath

from src.services.entorno_oracle import ArchivoNoLegible, EntornoOracle, OperacionEntornoFallida, Salida

RUTA_TEMPORAL = "/tmp/herramienta.tmp"


class EntornoFalso(EntornoOracle):
    """Registra lo que los servicios piden al entorno, sin ejecutar nada."""

    tipo_ruta = PurePosixPath

    def __init__(self, codigo=0, texto="", log="", salidas=None, fallo_permisos=None):
        self.codigo = codigo
        self.texto = texto
        self.log = log
        # salidas: una por ejecución de herramienta, en orden; sin ella se repite codigo/texto
        self.salidas = list(salidas) if salidas else None
        self.herramientas = []
        self.lecturas = []
        self.carpetas = []
        self.permisos = []
        # fallo_permisos: texto con el que dar_permisos_a_oracle lanza OperacionEntornoFallida
        self.fallo_permisos = fallo_permisos

    def crear_carpeta(self, ruta):
        self.carpetas.append(ruta)

    def dar_permisos_a_oracle(self, ruta):
        self.permisos.append(ruta)
        if self.fallo_permisos is not None:
            raise OperacionEntornoFallida(self.fallo_permisos)

    def leer_archivo(self, ruta):
        self.lecturas.append(ruta)
        # log=None simula un log que el entorno no puede leer
        if self.log is None:
            raise ArchivoNoLegible(str(ruta))
        return self.log

    def ejecutar(self, comando):
        self.herramientas.append(
            {
                "nombre": comando.nombre,
                "args": comando.args(RUTA_TEMPORAL),
                "script": comando.script,
                "prefijo": comando.prefijo,
                "extension": comando.extension,
                "variables": comando.variables,
            }
        )
        if self.salidas:
            return self.salidas[len(self.herramientas) - 1]
        return Salida(codigo=self.codigo, texto=self.texto)
