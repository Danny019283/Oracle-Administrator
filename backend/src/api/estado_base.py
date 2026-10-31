import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.dependencias import obtener_entorno
from src.api.respaldos import respuesta_herramienta_no_disponible
from src.services.entorno_oracle import HerramientaNoDisponible
from src.services.estado_base import AccionNoValida, EstadoBaseFallido, cambiar_estado, estado_actual

# Sin sesión por decisión explícita (RNF-6): la autenticación es la del SO dentro del entorno.
router = APIRouter(prefix="/base")


class SolicitudEstado(BaseModel):
    accion: Literal["APAGAR", "NOMOUNT", "MOUNT", "ENCENDER"]


def obtener_sid() -> str:
    return os.environ.get("ORACLE_SID") or "XE"


def _fallo(error: EstadoBaseFallido) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"mensaje": str(error), "explicacion": error.explicacion, "log": error.log},
    )


@router.get("/estado")
def get_estado(entorno=Depends(obtener_entorno), sid: str = Depends(obtener_sid)):
    try:
        return {"estado": estado_actual(entorno, sid)}
    except EstadoBaseFallido as error:
        return _fallo(error)
    except HerramientaNoDisponible as error:
        return respuesta_herramienta_no_disponible(error)


@router.post("/estado")
def post_estado(solicitud: SolicitudEstado, entorno=Depends(obtener_entorno), sid: str = Depends(obtener_sid)):
    try:
        log = cambiar_estado(entorno, sid, solicitud.accion)
    except AccionNoValida as error:
        raise HTTPException(status_code=409, detail=str(error))
    except EstadoBaseFallido as error:
        return _fallo(error)
    except HerramientaNoDisponible as error:
        return respuesta_herramienta_no_disponible(error)
    return {"mensaje": f"La acción {solicitud.accion} se ejecutó correctamente", "log": log}
