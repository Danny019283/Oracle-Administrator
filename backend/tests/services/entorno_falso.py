from pathlib import PurePosixPath

from src.services.entorno_oracle import ArchivoNoLegible, EntornoOracle, OperacionEntornoFallida, Salida

RUTA_TEMPORAL = "/tmp/herramienta.tmp"


class EntornoFalso(EntornoOracle):
    """Registra lo que los servicios piden al entorno, sin ejecutar nada."""

    tipo_ruta = PurePosixPath

    def __init__(
        self,
        codigo=0,
        texto="",
        log="",
        salidas=None,
        fallo_permisos=None,
        archivos=(),
        fallo_listado=None,
        fallo_borrado=None,
    ):
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
        self.archivos = archivos
        self.fallo_listado = fallo_listado
        self.fallo_borrado = fallo_borrado
        self.listados = []
        self.borrados = []

    def crear_carpeta(self, ruta):
        self.carpetas.append(ruta)

    def dar_permisos_a_oracle(self, ruta, sid):
        self.permisos.append((ruta, sid))
        if self.fallo_permisos is not None:
            raise OperacionEntornoFallida(self.fallo_permisos)

    def leer_archivo(self, ruta):
        self.lecturas.append(ruta)
        # log=None simula un log que el entorno no puede leer
        if self.log is None:
            raise ArchivoNoLegible(str(ruta))
        return self.log

    def listar_archivos(self, ruta):
        self.listados.append(ruta)
        if self.fallo_listado is not None:
            raise OperacionEntornoFallida(self.fallo_listado)
        # archivos: lista de ArchivoEntorno, o dict ruta -> lista para configurar cada carpeta
        if isinstance(self.archivos, dict):
            return list(self.archivos.get(ruta, []))
        return list(self.archivos)

    def borrar_archivo(self, ruta):
        self.borrados.append(ruta)
        if self.fallo_borrado is not None:
            raise OperacionEntornoFallida(self.fallo_borrado)

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
