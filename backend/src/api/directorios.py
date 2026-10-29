from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.api.dependencias import obtener_entorno
from src.services import directorios

router = APIRouter(prefix="/directorios")


class SolicitudDirectorio(BaseModel):
    nombre: str = ""
    ruta: str = ""
    schema: str | None = None


@router.get("")
def get_directorios(consulta=Depends(obtener_consulta_admin), entorno=Depends(obtener_entorno)):
    return responder(
        lambda: {
            "directorios": directorios.listar_todos_directorios(consulta),
            "ejemplos_ruta": directorios.ejemplos_ruta(entorno.tipo_ruta),
        }
    )


@router.post("")
def post_directorio(
    solicitud: SolicitudDirectorio,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
    entorno=Depends(obtener_entorno),
):
    def crear():
        nombre = directorios.crear_directorio(
            consulta, sentencia, entorno, solicitud.nombre, solicitud.ruta, solicitud.schema
        )
        return {"mensaje": f"Directorio {nombre} creado"}

    return responder(crear)


@router.put("/{nombre}")
def put_directorio(
    nombre: str,
    solicitud: SolicitudDirectorio,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
    entorno=Depends(obtener_entorno),
):
    def editar():
        directorios.editar_directorio(consulta, sentencia, entorno, nombre, solicitud.ruta)
        return {"mensaje": f"Directorio {nombre.strip().upper()} actualizado"}

    return responder(editar)


@router.delete("/{nombre}")
def delete_directorio(
    nombre: str,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def eliminar():
        directorios.eliminar_directorio(consulta, sentencia, nombre)
        return {"mensaje": f"Directorio {nombre.strip().upper()} eliminado"}

    return responder(eliminar)
