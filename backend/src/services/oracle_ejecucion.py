from collections.abc import Callable, Sequence
from typing import Any

from src.services.expdp_runner import Conexion
from src.services.oracle_conexion import abrir_conexion

Sentencia = Callable[..., None]


def sentencia_oracle(conexion: Conexion) -> Sentencia:
    """Ejecuta sentencias que no devuelven filas (DDL, GRANT, ALTER ...) con la sesión."""

    def ejecutar(sql: str, params: dict[str, Any] | None = None) -> None:
        with abrir_conexion(conexion) as bd:
            with bd.cursor() as cursor:
                cursor.execute(sql, params or {})
            bd.commit()

    return ejecutar


Paso = tuple[str, dict[str, Any] | None]
Sesion = Callable[[Sequence[Paso]], list[list[Any] | None]]


def sesion_oracle(conexion: Conexion) -> Sesion:
    """Ejecuta varios pasos en una misma sesión y devuelve las filas de cada uno.

    Hace falta cuando un paso deja datos que solo ve esa sesión, como
    EXPLAIN PLAN, que escribe en la tabla temporal PLAN_TABLE.
    """

    def ejecutar(pasos: Sequence[Paso]) -> list[list[Any] | None]:
        resultados: list[list[Any] | None] = []
        with abrir_conexion(conexion) as bd:
            with bd.cursor() as cursor:
                for sql, params in pasos:
                    cursor.execute(sql, params or {})
                    resultados.append(cursor.fetchall() if cursor.description else None)
        return resultados

    return ejecutar
