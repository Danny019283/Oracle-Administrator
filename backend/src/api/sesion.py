from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services.login import (
    LoginFallido,
    SolicitudInvalida,
    conectar_oracle,
    iniciar_sesion,
    validar_login,
)
from src.services.sesiones import AlmacenSesiones

router = APIRouter(prefix="/sesion")

_ALMACEN = AlmacenSesiones()


def obtener_almacen() -> AlmacenSesiones:
    return _ALMACEN


def obtener_conector():
    return conectar_oracle


def token_de(authorization: str | None = Header(default=None)) -> str:
    esquema, _, token = (authorization or "").partition(" ")
    if esquema != "Bearer" or not token:
        raise HTTPException(status_code=401, detail="Falta el token de sesión")
    return token


class SolicitudSesion(BaseModel):
    host: str = ""
    puerto: int | str = ""
    servicio: str = ""
    usuario: str = ""
    password: str = ""
    sysdba: bool = False


@router.post("")
def post_sesion(
    solicitud: SolicitudSesion,
    almacen: AlmacenSesiones = Depends(obtener_almacen),
    conector=Depends(obtener_conector),
):
    try:
        pedido = validar_login(**solicitud.model_dump())
    except SolicitudInvalida as error:
        return JSONResponse(status_code=422, content={"errores": error.errores})
    try:
        sesion = iniciar_sesion(pedido, almacen, conector)
    except LoginFallido as fallo:
        return JSONResponse(
            status_code=502 if fallo.inalcanzable else 401,
            content={"mensaje": fallo.mensaje, "codigo": fallo.codigo},
        )
    return {"token": sesion.token, "usuario": sesion.usuario, "sysdba": sesion.sysdba}


@router.delete("", status_code=204)
def delete_sesion(
    token: str = Depends(token_de),
    almacen: AlmacenSesiones = Depends(obtener_almacen),
):
    if almacen.resolver(token) is None:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    almacen.cerrar(token)
    return Response(status_code=204)
