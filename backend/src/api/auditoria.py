from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.services import auditoria

router = APIRouter(prefix="/auditoria")


class SolicitudPolitica(BaseModel):
    nombre: str = ""
    tipo: str = "tabla"
    acciones: list[str] = []
    schema_tabla: str = ""
    tabla: str = ""
    habilitar: bool = True


class SolicitudEliminar(BaseModel):
    confirmar: bool = False


@router.get("/estado")
def get_estado(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: auditoria.estado(consulta))


@router.get("/politicas")
def get_politicas(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"politicas": auditoria.listar_politicas(consulta)})


@router.get("/tablas")
def get_tablas(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"tablas": auditoria.listar_tablas_auditables(consulta)})


@router.post("/politicas")
def post_politica(solicitud: SolicitudPolitica, sentencia=Depends(obtener_sentencia)):
    def crear():
        nombre = auditoria.crear_politica(
            sentencia,
            nombre=solicitud.nombre,
            tipo=solicitud.tipo,
            acciones=solicitud.acciones,
            schema=solicitud.schema_tabla,
            tabla=solicitud.tabla,
            habilitar=solicitud.habilitar,
        )
        estado = "creada y habilitada" if solicitud.habilitar else "creada"
        return {"mensaje": f"Política {nombre} {estado}"}

    return responder(crear)


@router.post("/politicas/{nombre}/habilitar")
def post_habilitar(nombre: str, sentencia=Depends(obtener_sentencia)):
    return responder(
        lambda: {"mensaje": f"Política {auditoria.habilitar_politica(sentencia, nombre)} habilitada"}
    )


@router.post("/politicas/{nombre}/deshabilitar")
def post_deshabilitar(nombre: str, sentencia=Depends(obtener_sentencia)):
    return responder(
        lambda: {
            "mensaje": f"Política {auditoria.deshabilitar_politica(sentencia, nombre)} deshabilitada"
        }
    )


@router.post("/politicas/{nombre}/eliminar")
def post_eliminar(nombre: str, solicitud: SolicitudEliminar, sentencia=Depends(obtener_sentencia)):
    if not solicitud.confirmar:
        return JSONResponse(
            status_code=422,
            content={"errores": ["Debes confirmar que quieres eliminar la política"]},
        )
    return responder(
        lambda: {"mensaje": f"Política {auditoria.eliminar_politica(sentencia, nombre)} eliminada"}
    )


@router.get("/registros")
def get_registros(
    politica: str = "",
    usuario: str = "",
    limite: int = 100,
    consulta=Depends(obtener_consulta_admin),
):
    return responder(
        lambda: {"registros": auditoria.registros(consulta, politica, usuario, limite)}
    )
