from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.admin_comun import (
    obtener_consulta_admin,
    obtener_sentencia,
    obtener_sesion,
    responder,
)
from src.services import tuning

router = APIRouter(prefix="/tuning")


# «schema» choca con un atributo de BaseModel, así que el campo se llama schema_
# y el JSON lo trae con su nombre normal mediante el alias.


class SolicitudPlan(BaseModel):
    sql: str = ""
    schema_: str = Field("", alias="schema")


class SolicitudEstadisticas(BaseModel):
    schema_: str = Field("", alias="schema")
    tabla: str = ""


class SolicitudIndice(BaseModel):
    schema_: str = Field("", alias="schema")
    tabla: str = ""
    nombre: str = ""
    columnas: list[str] = []
    unico: bool = False
    tablespace: str = ""


class SolicitudEliminarIndice(BaseModel):
    schema_: str = Field("", alias="schema")
    tabla: str = ""
    nombre: str = ""
    confirmar: bool = False


@router.get("/catalogos")
def get_catalogos(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: tuning.catalogos(consulta))


@router.post("/plan")
def post_plan(
    solicitud: SolicitudPlan,
    consulta=Depends(obtener_consulta_admin),
    sesion=Depends(obtener_sesion),
):
    return responder(lambda: tuning.plan_ejecucion(consulta, sesion, solicitud.sql, solicitud.schema_))


@router.get("/tablas")
def get_tablas(schema: str = "", consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"tablas": tuning.listar_tablas(consulta, schema)})


@router.post("/estadisticas")
def post_estadisticas(
    solicitud: SolicitudEstadisticas,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def recolectar():
        objetivo = tuning.recolectar_estadisticas(consulta, sentencia, solicitud.schema_, solicitud.tabla)
        return {"mensaje": f"Estadísticas de {objetivo} actualizadas"}

    return responder(recolectar)


@router.get("/indices")
def get_indices(schema: str = "", tabla: str = "", consulta=Depends(obtener_consulta_admin)):
    return responder(
        lambda: {
            "indices": tuning.listar_indices(consulta, schema, tabla),
            "columnas": tuning.listar_columnas(consulta, schema, tabla),
        }
    )


@router.post("/indices")
def post_indice(
    solicitud: SolicitudIndice,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def crear():
        nombre = tuning.crear_indice(
            consulta,
            sentencia,
            schema=solicitud.schema_,
            tabla=solicitud.tabla,
            nombre=solicitud.nombre,
            columnas=solicitud.columnas,
            unico=solicitud.unico,
            tablespace=solicitud.tablespace,
        )
        return {"mensaje": f"Índice {nombre} creado"}

    return responder(crear)


@router.post("/indices/eliminar")
def post_eliminar_indice(
    solicitud: SolicitudEliminarIndice,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    if not solicitud.confirmar:
        return JSONResponse(
            status_code=422,
            content={"errores": ["Debes confirmar que quieres eliminar el índice"]},
        )

    def eliminar():
        nombre = tuning.eliminar_indice(
            consulta, sentencia, solicitud.schema_, solicitud.tabla, solicitud.nombre
        )
        return {"mensaje": f"Índice {nombre} eliminado"}

    return responder(eliminar)
