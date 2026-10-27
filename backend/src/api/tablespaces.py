from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.services import tablespaces

router = APIRouter(prefix="/tablespaces")


class SolicitudArchivo(BaseModel):
    archivo: str = ""
    tamano: str = "100M"
    autoextend: bool = True
    siguiente: str = "10M"
    maximo: str = "UNLIMITED"


class SolicitudTablespace(SolicitudArchivo):
    nombre: str = ""
    tipo: str = "PERMANENT"


class SolicitudRedimensionar(BaseModel):
    tamano: str = ""


class SolicitudAutoextend(BaseModel):
    autoextend: bool = True
    siguiente: str = "10M"
    maximo: str = "UNLIMITED"


class SolicitudEstado(BaseModel):
    estado: str = ""
    confirmar: bool = False


@router.get("")
def get_tablespaces(consulta=Depends(obtener_consulta_admin)):
    return responder(
        lambda: {
            "tablespaces": tablespaces.listar_tablespaces(consulta),
            "carpeta": tablespaces.carpeta_datafiles(consulta),
        }
    )


@router.get("/{tablespace}")
def get_tablespace(tablespace: str, consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: tablespaces.detalle_tablespace(consulta, tablespace))


@router.post("")
def post_tablespace(
    solicitud: SolicitudTablespace,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def crear():
        nombre = tablespaces.crear_tablespace(
            consulta,
            sentencia,
            nombre=solicitud.nombre,
            tipo=solicitud.tipo,
            archivo=solicitud.archivo,
            tamano=solicitud.tamano,
            autoextend=solicitud.autoextend,
            siguiente=solicitud.siguiente,
            maximo=solicitud.maximo,
        )
        return {"mensaje": f"Tablespace {nombre} creado"}

    return responder(crear)


@router.post("/{tablespace}/archivos")
def post_archivo(
    tablespace: str,
    solicitud: SolicitudArchivo,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def agregar():
        nombre = tablespaces.agregar_archivo(
            consulta,
            sentencia,
            tablespace,
            archivo=solicitud.archivo,
            tamano=solicitud.tamano,
            autoextend=solicitud.autoextend,
            siguiente=solicitud.siguiente,
            maximo=solicitud.maximo,
        )
        return {"mensaje": f"Archivo {solicitud.archivo.strip().lower()} agregado a {nombre}"}

    return responder(agregar)


@router.post("/{tablespace}/archivos/{file_id}/redimensionar")
def post_redimensionar(
    tablespace: str,
    file_id: int,
    solicitud: SolicitudRedimensionar,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def redimensionar():
        tablespaces.redimensionar_archivo(consulta, sentencia, tablespace, file_id, solicitud.tamano)
        return {"mensaje": f"Archivo {file_id} redimensionado a {solicitud.tamano.strip().upper()}"}

    return responder(redimensionar)


@router.post("/{tablespace}/archivos/{file_id}/autoextend")
def post_autoextend(
    tablespace: str,
    file_id: int,
    solicitud: SolicitudAutoextend,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def cambiar():
        tablespaces.cambiar_autoextend(
            consulta,
            sentencia,
            tablespace,
            file_id,
            solicitud.autoextend,
            solicitud.siguiente,
            solicitud.maximo,
        )
        accion = "activado" if solicitud.autoextend else "desactivado"
        return {"mensaje": f"AUTOEXTEND {accion} en el archivo {file_id}"}

    return responder(cambiar)


@router.post("/{tablespace}/estado")
def post_estado(
    tablespace: str,
    solicitud: SolicitudEstado,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    estado = " ".join(solicitud.estado.split()).upper()
    if estado == "OFFLINE" and not solicitud.confirmar:
        return JSONResponse(
            status_code=422,
            content={"errores": ["Debes confirmar que quieres poner el tablespace OFFLINE"]},
        )

    def cambiar():
        nombre = tablespaces.cambiar_estado(consulta, sentencia, tablespace, estado)
        return {"mensaje": f"Tablespace {nombre} ahora está {estado}"}

    return responder(cambiar)
