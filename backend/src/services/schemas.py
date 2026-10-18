from collections.abc import Callable, Sequence
from typing import Any

Consulta = Callable[..., Sequence[Sequence[Any]]]


class SinSchemas(Exception):
    pass


def listar_schemas(consulta: Consulta) -> list[str]:
    filas = consulta(
        "SELECT username FROM all_users WHERE oracle_maintained = 'N' ORDER BY username"
    )
    if not filas:
        raise SinSchemas("No hay schemas de usuario")
    return [fila[0] for fila in filas]
