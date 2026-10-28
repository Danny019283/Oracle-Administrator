from fastapi import Depends, HTTPException

from src.api.sesion import obtener_almacen, token_de
from src.services.entorno_oracle import EntornoOracle
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones

_ENTORNO: EntornoOracle | None = None


def fijar_entorno(entorno: EntornoOracle) -> None:
    global _ENTORNO
    _ENTORNO = entorno


def obtener_entorno() -> EntornoOracle:
    return _ENTORNO


def obtener_conexion(
    token: str = Depends(token_de),
    almacen: AlmacenSesiones = Depends(obtener_almacen),
) -> Conexion:
    conexion = almacen.resolver(token)
    if conexion is None:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    return conexion
