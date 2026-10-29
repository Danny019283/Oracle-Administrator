from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.api.dependencias import obtener_conexion, obtener_entorno
from src.services import directorios

router = APIRouter(prefix="/directorios")


class SolicitudDirectorio(BaseModel):
    nombre: str = ""
    ruta: str = ""


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
    conexion=Depends(obtener_conexion),
):
    def crear():
        nombre = directorios.crear_directorio(
            consulta, sentencia, entorno, conexion.usuario, solicitud.nombre, solicitud.ruta
        )
        return {"mensaje": f"Directorio {nombre} creado"}

    return responder(crear)
