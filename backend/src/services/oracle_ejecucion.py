from collections.abc import Callable, Sequence
from typing import Any

import oracledb

from src.services.expdp_runner import Conexion

Sentencia = Callable[..., None]


def _conectar(conexion: Conexion):
    """Abre la conexión de la sesión: su host, puerto y servicio, como SYSDBA si lo es."""
    modo = oracledb.AUTH_MODE_SYSDBA if conexion.sysdba else oracledb.AUTH_MODE_DEFAULT
    return oracledb.connect(
        user=conexion.usuario,
        password=conexion.password,
        dsn=f"{conexion.host}:{conexion.puerto}/{conexion.servicio}",
        mode=modo,
    )


def sentencia_oracle(conexion: Conexion) -> Sentencia:
    """Ejecuta sentencias que no devuelven filas (DDL, GRANT, ALTER ...) con la sesión."""

    def ejecutar(sql: str, params: dict[str, Any] | None = None) -> None:
        with _conectar(conexion) as bd:
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
        with _conectar(conexion) as bd:
            with bd.cursor() as cursor:
                for sql, params in pasos:
                    cursor.execute(sql, params or {})
                    resultados.append(cursor.fetchall() if cursor.description else None)
        return resultados

    return ejecutar
