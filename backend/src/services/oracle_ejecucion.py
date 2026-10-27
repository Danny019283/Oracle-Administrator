from collections.abc import Callable
from typing import Any

import oracledb

from src.services.expdp_runner import Conexion

Sentencia = Callable[..., None]


def sentencia_oracle(conexion: Conexion) -> Sentencia:
    """Ejecuta sentencias que no devuelven filas (DDL, GRANT, ALTER ...) con la sesión."""
    modo = oracledb.AUTH_MODE_SYSDBA if conexion.sysdba else oracledb.AUTH_MODE_DEFAULT

    def ejecutar(sql: str, params: dict[str, Any] | None = None) -> None:
        with oracledb.connect(
            user=conexion.usuario,
            password=conexion.password,
            dsn=f"{conexion.host}:{conexion.puerto}/{conexion.servicio}",
            mode=modo,
        ) as bd:
            with bd.cursor() as cursor:
                cursor.execute(sql, params or {})
            bd.commit()

    return ejecutar
