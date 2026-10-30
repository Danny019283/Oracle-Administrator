import re
from dataclasses import dataclass, field, replace
from datetime import datetime

from src.services.directorios import Consulta, DirectorioNoEncontrado, listar_todos_directorios
from src.services.identificadores import IdentificadorInvalido, normalizar_identificador
from src.services.entorno_oracle import (
    ArchivoEntorno,
    ArchivoNoLegible,
    EntornoOracle,
    HerramientaNoDisponible,
    OperacionEntornoFallida,
)
from src.services.errores_oracle import explicar_error
from src.services.respaldo_full import AdvertenciaLimpieza
from src.services.rman_runner import ejecutar_rman

_BASE = r"(?P<base>[A-Za-z0-9_-]{1,50}_(?P<marca>\d{8}_\d{6}))"
# .dmp/.log son `<base>.<ext>`; la pieza RMAN es `<base>_<DB>_<set>_<pieza>.dbf` con DB sin '_',
# así `_<DB>_<n>_<n>` solo casa al final y no se confunde con una marca de tiempo dentro del nombre.
_ARCHIVO = re.compile(rf"{_BASE}(?:\.(?:dmp|log)|_[A-Za-z0-9$#]+_\d+_\d+\.dbf)")


class RespaldoInvalido(Exception):
    pass


class RespaldoNoEncontrado(Exception):
    pass


_BASE_VALIDA = re.compile(r"[A-Za-z0-9_-]+_\d{8}_\d{6}")


@dataclass(frozen=True)
class ResultadoEliminacion:
    tipo: str
    advertencia: AdvertenciaLimpieza | None = None


# Sin entrada del cliente: solo descarta del catálogo de RMAN las piezas que acabamos de borrar.
_SCRIPT_LIMPIEZA = "CROSSCHECK BACKUP;\nDELETE NOPROMPT EXPIRED BACKUP;\n"


def eliminar_respaldo(
    consulta: Consulta, entorno: EntornoOracle, directorio: str, base: str, sid: str
) -> ResultadoEliminacion:
    """Borra los archivos de un respaldo y devuelve su tipo, con advertencia si falla la limpieza RMAN.

    Los nombres a borrar salen del listado del directorio, nunca de la entrada del cliente.
    """
    if not _BASE_VALIDA.fullmatch(base):
        raise RespaldoInvalido("El identificador del respaldo no es válido")
    try:
        nombre = normalizar_identificador(directorio, "el directorio")
    except IdentificadorInvalido:
        raise DirectorioNoEncontrado(f"No existe el directorio {directorio}")
    ruta = next((d.ruta for d in listar_todos_directorios(consulta) if d.nombre == nombre), None)
    if ruta is None:
        raise DirectorioNoEncontrado(f"No existe el directorio {nombre}")

    carpeta = entorno.tipo_ruta(ruta)
    respaldo = next((r for r in agrupar_archivos(entorno.listar_archivos(carpeta)) if r.base == base), None)
    if respaldo is None:
        raise RespaldoNoEncontrado("Respaldo no encontrado")
    for archivo in respaldo.archivos:
        entorno.borrar_archivo(carpeta / archivo.nombre)
    if respaldo.tipo != "RMAN":
        return ResultadoEliminacion(respaldo.tipo)
    # Los archivos ya están borrados: si RMAN falla o no está, es advertencia, no error.
    try:
        limpieza = ejecutar_rman(entorno, _SCRIPT_LIMPIEZA, sid)
    except HerramientaNoDisponible as error:
        return ResultadoEliminacion("RMAN", AdvertenciaLimpieza(explicar_error(str(error)), str(error)))
    if limpieza.codigo != 0:
        return ResultadoEliminacion("RMAN", AdvertenciaLimpieza(explicar_error(limpieza.texto), limpieza.texto))
    return ResultadoEliminacion("RMAN")


@dataclass(frozen=True, kw_only=True)
class Respaldo:
    directorio: str = ""
    ruta: str = ""
    base: str
    tipo: str
    estado: str | None = None
    archivos: list[ArchivoEntorno] = field(default_factory=list)
    tamano: int
    fecha: datetime


_EXITO = {"Data Pump": "successfully completed", "RMAN": "Finished backup"}


def estado_de(respaldo: Respaldo, entorno: EntornoOracle, ruta: str) -> str:
    nombre_log = f"{respaldo.base}.log"
    if not any(a.nombre == nombre_log for a in respaldo.archivos):
        return "Sin log"
    try:
        log = entorno.leer_archivo(entorno.tipo_ruta(ruta) / nombre_log)
    except ArchivoNoLegible:
        return "Sin log"
    if "ORA-" in log or "RMAN-" in log:
        return "Con errores"
    if respaldo.tipo == "Desconocido":
        return "Sin respaldo"
    return "Completo" if _EXITO[respaldo.tipo] in log else "Sin log"


def agrupar_archivos(archivos: list[ArchivoEntorno]) -> list[Respaldo]:
    grupos: dict[str, list[ArchivoEntorno]] = {}
    fechas: dict[str, datetime] = {}
    for a in archivos:
        m = _ARCHIVO.fullmatch(a.nombre)
        if not m:
            continue
        try:
            fecha = datetime.strptime(m["marca"], "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        grupos.setdefault(m["base"], []).append(a)
        fechas[m["base"]] = fecha

    respaldos = []
    for base, lista in grupos.items():
        extensiones = {a.nombre.rsplit(".", 1)[1] for a in lista}
        tipo = (
            "Data Pump" if "dmp" in extensiones else "RMAN" if "dbf" in extensiones else "Desconocido"
        )
        respaldos.append(
            Respaldo(
                base=base,
                tipo=tipo,
                archivos=lista,
                tamano=sum(a.tamano for a in lista),
                fecha=fechas[base],
            )
        )
    return sorted(respaldos, key=lambda r: r.fecha, reverse=True)


def listar_respaldos(consulta: Consulta, entorno: EntornoOracle) -> tuple[list[Respaldo], list[str]]:
    respaldos: list[Respaldo] = []
    avisos: list[str] = []
    for d in listar_todos_directorios(consulta):
        try:
            archivos = entorno.listar_archivos(entorno.tipo_ruta(d.ruta))
        except OperacionEntornoFallida:
            avisos.append(f"No se pudo leer el directorio {d.nombre} ({d.ruta})")
            continue
        respaldos += [
            replace(r, directorio=d.nombre, ruta=d.ruta, estado=estado_de(r, entorno, d.ruta))
            for r in agrupar_archivos(archivos)
        ]
    return sorted(respaldos, key=lambda r: r.fecha, reverse=True), avisos
