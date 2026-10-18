from collections.abc import Callable, Sequence
from dataclasses import dataclass
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


class SinDirectorios(Exception):
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
