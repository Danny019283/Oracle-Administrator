from collections.abc import Callable, Sequence
from typing import Any

import oracledb

from src.services.expdp_runner import Conexion


def consulta_oracle(
    conexion: Conexion, driver: Any = oracledb
) -> Callable[..., Sequence[Sequence[Any]]]:
    modo = driver.AUTH_MODE_SYSDBA if conexion.sysdba else driver.AUTH_MODE_DEFAULT

    def consulta(sql: str, params: dict[str, Any] | None = None):
        with driver.connect(
            user=conexion.usuario,
            password=conexion.password,
            dsn=f"{conexion.host}:{conexion.puerto}/{conexion.servicio}",
            mode=modo,
        ) as bd:
            with bd.cursor() as cursor:
                cursor.execute(sql, params or {})
                return cursor.fetchall()

    return consulta
