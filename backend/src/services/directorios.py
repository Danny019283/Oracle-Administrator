from collections.abc import Callable, Sequence
import re
from dataclasses import dataclass
from pathlib import PurePath, PureWindowsPath
from typing import Any

Consulta = Callable[..., Sequence[Sequence[Any]]]

_SQL = """
SELECT d.directory_name, d.directory_path
FROM all_directories d
WHERE EXISTS (SELECT 1 FROM all_tab_privs p
              WHERE p.table_name = d.directory_name AND p.privilege = 'READ')
  AND EXISTS (SELECT 1 FROM all_tab_privs p
              WHERE p.table_name = d.directory_name AND p.privilege = 'WRITE')
ORDER BY d.directory_name
"""

_SQL_TODOS = """
SELECT directory_name, directory_path
FROM all_directories
ORDER BY directory_name
"""


class SinDirectorios(Exception):
    pass


class DirectorioInvalido(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


class DirectorioNoEncontrado(Exception):
    pass


@dataclass(frozen=True)
class Directorio:
    nombre: str
    ruta: str


def listar_directorios(consulta: Consulta) -> list[Directorio]:
    filas = consulta(_SQL)
    if not filas:
        raise SinDirectorios(
            "No hay directorios disponibles. Debes crear uno desde esta pantalla para poder respaldar"
        )
    return [Directorio(nombre=nombre, ruta=ruta) for nombre, ruta in filas]


def listar_todos_directorios(consulta: Consulta) -> list[Directorio]:
    return [Directorio(nombre=nombre, ruta=ruta) for nombre, ruta in consulta(_SQL_TODOS)]


_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def validar_ruta(ruta: str, tipo_ruta: type[PurePath]) -> list[str]:
    if not ruta:
        return ["La ruta es obligatoria"]
    errores = []
    if not tipo_ruta(ruta).is_absolute():
        errores.append("La ruta debe ser absoluta")
    if len(ruta) > 4000:
        errores.append("La ruta no puede superar los 4000 caracteres")
    if "'" in ruta:
        errores.append("La ruta no puede contener comillas simples")
    if _CONTROL.search(ruta):
        errores.append("La ruta no puede contener caracteres de control")
    return errores


def ejemplos_ruta(tipo_ruta: type[PurePath]) -> list[str]:
    if issubclass(tipo_ruta, PureWindowsPath):
        return ["C:\\respaldos", "\\\\servidor\\recurso"]
    return ["/opt/oracle/respaldos"]
