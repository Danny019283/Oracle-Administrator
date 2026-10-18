from collections.abc import Callable, Sequence
from typing import Any

Consulta = Callable[..., Sequence[Sequence[Any]]]


class SinTablas(Exception):
    pass


def listar_tablas(consulta: Consulta) -> list[str]:
    filas = consulta("SELECT table_name FROM user_tables ORDER BY table_name")
    if not filas:
        raise SinTablas("No hay tablas en el schema")
    return [fila[0] for fila in filas]
