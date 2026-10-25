import os
from collections.abc import Callable
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
