import os
from collections.abc import Callable, Sequence
from typing import Any

import oracledb

from src.services.expdp_runner import Conexion

Sentencia = Callable[..., None]


def sentencia_oracle(conexion: Conexion) -> Sentencia:
    """Ejecuta sentencias que no devuelven filas (DDL, GRANT, ALTER ...)."""
    host = os.environ.get("ORACLE_HOST", "localhost")
    puerto = os.environ.get("ORACLE_PORT", "1521")

    def ejecutar(sql: str, params: dict[str, Any] | None = None) -> None:
        with oracledb.connect(
            user=conexion.usuario,
            password=conexion.password,
            dsn=f"{host}:{puerto}/{conexion.servicio}",
        ) as bd:
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
    host = os.environ.get("ORACLE_HOST", "localhost")
    puerto = os.environ.get("ORACLE_PORT", "1521")

    def ejecutar(pasos: Sequence[Paso]) -> list[list[Any] | None]:
        resultados: list[list[Any] | None] = []
        with oracledb.connect(
            user=conexion.usuario,
            password=conexion.password,
            dsn=f"{host}:{puerto}/{conexion.servicio}",
        ) as bd:
            with bd.cursor() as cursor:
                for sql, params in pasos:
                    cursor.execute(sql, params or {})
                    resultados.append(cursor.fetchall() if cursor.description else None)
        return resultados

    return ejecutar
