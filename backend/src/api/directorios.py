from fastapi import APIRouter, Depends

from src.api.admin_comun import obtener_consulta_admin, responder
from src.api.dependencias import obtener_entorno
from src.services import directorios

router = APIRouter(prefix="/directorios")


@router.get("")
def get_directorios(consulta=Depends(obtener_consulta_admin), entorno=Depends(obtener_entorno)):
    return responder(
        lambda: {
            "directorios": directorios.listar_todos_directorios(consulta),
            "ejemplos_ruta": directorios.ejemplos_ruta(entorno.tipo_ruta),
        }
    )
