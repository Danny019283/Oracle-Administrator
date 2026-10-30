import re
from dataclasses import dataclass, field, replace
from datetime import datetime

from src.services.directorios import Consulta, listar_todos_directorios
from src.services.entorno_oracle import (
    ArchivoEntorno,
    ArchivoNoLegible,
    EntornoOracle,
    OperacionEntornoFallida,
)

_BASE = r"(?P<base>[A-Za-z0-9_-]{1,50}_(?P<marca>\d{8}_\d{6}))"
# .dmp/.log son `<base>.<ext>`; la pieza RMAN es `<base>_<DB>_<set>_<pieza>.dbf` con DB sin '_',
# así `_<DB>_<n>_<n>` solo casa al final y no se confunde con una marca de tiempo dentro del nombre.
_ARCHIVO = re.compile(rf"{_BASE}(?:\.(?:dmp|log)|_[A-Za-z0-9$#]+_\d+_\d+\.dbf)")


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
