import re
from dataclasses import dataclass
from datetime import datetime

_NOMBRE_VALIDO = re.compile(r"[A-Za-z0-9_-]{1,50}")


class NombreInvalido(ValueError):
    pass


@dataclass(frozen=True)
class NombresDump:
    dmp: str
    log: str


def construir_base(nombre: str, ahora: datetime) -> str:
    if not _NOMBRE_VALIDO.fullmatch(nombre):
        raise NombreInvalido(
            "El nombre admite letras, números, '_' y '-', de 1 a 50 caracteres"
        )
    return f"{nombre}_{ahora:%Y%m%d_%H%M%S}"


def construir_nombres(nombre: str, ahora: datetime) -> NombresDump:
    base = construir_base(nombre, ahora)
    return NombresDump(dmp=f"{base}.dmp", log=f"{base}.log")
