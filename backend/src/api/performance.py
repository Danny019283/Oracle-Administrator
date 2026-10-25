from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.services import performance

router = APIRouter(prefix="/performance")


class SolicitudTerminar(BaseModel):
    sid: int
    serial: int
    confirmar: bool = False


@router.get("/resumen")
def get_resumen(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: performance.resumen(consulta))


@router.get("/sesiones")
def get_sesiones(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"sesiones": performance.listar_sesiones(consulta)})


@router.get("/consultas")
def get_consultas(limite: int = 10, consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"consultas": performance.consultas_costosas(consulta, limite)})


@router.get("/esperas")
def get_esperas(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"esperas": performance.principales_esperas(consulta)})


@router.post("/sesiones/terminar")
def post_terminar(solicitud: SolicitudTerminar, sentencia=Depends(obtener_sentencia)):
    if not solicitud.confirmar:
        return JSONResponse(
            status_code=422,
            content={"errores": ["Debes confirmar que quieres terminar la sesión"]},
        )

    def terminar():
        performance.terminar_sesion(sentencia, solicitud.sid, solicitud.serial)
        return {"mensaje": f"Sesión {solicitud.sid},{solicitud.serial} terminada"}

    return responder(terminar)
