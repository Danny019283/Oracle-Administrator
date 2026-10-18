import os
from collections.abc import Callable, Sequence
from typing import Any

import oracledb

from src.services.expdp_runner import Conexion


def consulta_oracle(conexion: Conexion) -> Callable[..., Sequence[Sequence[Any]]]:
    host = os.environ.get("ORACLE_HOST", "localhost")
    puerto = os.environ.get("ORACLE_PORT", "1521")

    def consulta(sql: str, params: dict[str, Any] | None = None):
        with oracledb.connect(
            user=conexion.usuario,
            password=conexion.password,
            dsn=f"{host}:{puerto}/{conexion.servicio}",
        ) as bd:
            with bd.cursor() as cursor:
                cursor.execute(sql, params or {})
                return cursor.fetchall()

    return consulta
