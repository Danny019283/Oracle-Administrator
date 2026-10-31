from pathlib import PurePosixPath

from src.services.entorno_oracle import (
    ArchivoNoLegible,
    EntornoOracle,
    HerramientaNoDisponible,
    OperacionEntornoFallida,
    Salida,
)

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
        fallo_escritura=None,
        salidas_archivo=None,
        herramienta_ausente=None,
        variables_entorno=None,
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
        # fallo_escritura: texto con el que escribir_archivo lanza OperacionEntornoFallida
        self.fallo_escritura = fallo_escritura
        self.escrituras = []
        # salidas_archivo: ruta -> Salida de ejecutar_archivo; sin ella se usa codigo/texto
        self.salidas_archivo = salidas_archivo or {}
        # herramienta_ausente: nombre con el que ejecutar_archivo lanza HerramientaNoDisponible
        self.herramienta_ausente = herramienta_ausente
        self.ejecuciones = []
        # variables_entorno: nombre -> valor de variable_de_entorno; las consultas quedan en `consultas_entorno`
        self.variables_entorno = variables_entorno or {}
        self.consultas_entorno = []

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

    def escribir_archivo(self, ruta, texto, ejecutable):
        if self.fallo_escritura is not None:
            raise OperacionEntornoFallida(self.fallo_escritura)
        self.escrituras.append((ruta, texto, ejecutable))

    def ejecutar_archivo(self, ruta):
        self.ejecuciones.append(ruta)
        if self.herramienta_ausente is not None:
            raise HerramientaNoDisponible(self.herramienta_ausente)
        return self.salidas_archivo.get(ruta, Salida(codigo=self.codigo, texto=self.texto))

    def variable_de_entorno(self, nombre):
        self.consultas_entorno.append(nombre)
        return self.variables_entorno.get(nombre)

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
