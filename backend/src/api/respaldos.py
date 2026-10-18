import os
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services.directorios import SinDirectorios, listar_directorios
from src.services.docker_ejecutor import ejecutar_docker
from src.services.expdp_runner import Conexion
from src.services.oracle_conexion import consulta_oracle
from src.services.respaldo import (
    SCHEMAS,
    TABLAS,
    RespaldoFallido,
    SinObjetos,
    SolicitudInvalida,
    TipoObjeto,
    respaldar,
    validar_solicitud,
)
from src.services.schemas import SinSchemas, listar_schemas
from src.services.tablas import SinTablas, listar_tablas

router = APIRouter(prefix="/respaldos")


def obtener_conexion(
    x_oracle_user: str = Header(),
    x_oracle_password: str = Header(),
    x_oracle_service: str = Header(),
) -> Conexion:
    return Conexion(
        usuario=x_oracle_user, password=x_oracle_password, servicio=x_oracle_service
    )


def obtener_consulta(conexion: Conexion = Depends(obtener_conexion)):
    return consulta_oracle(conexion)


def obtener_ejecutor():
    return ejecutar_docker


class SolicitudRespaldo(BaseModel):
    tablas: list[str] = []
    directorio: str = ""
    nombre: str = ""


class SolicitudRespaldoSchemas(BaseModel):
    schemas: list[str] = []
    directorio: str = ""
    nombre: str = ""


def _listado(clave: str, listar: Callable, sin_objetos: type[SinObjetos], consulta):
    try:
        return {clave: listar(consulta)}
    except sin_objetos as error:
        raise HTTPException(status_code=404, detail=str(error))


def _respaldo(
    tipo: TipoObjeto,
    listar: Callable,
    sin_objetos: type[SinObjetos],
    objetos: list[str],
    directorio: str,
    nombre: str,
    conexion: Conexion,
    consulta,
    ejecutar,
):
    try:
        disponibles = listar(consulta)
    except sin_objetos:
        disponibles = []
    try:
        directorios = listar_directorios(consulta)
    except SinDirectorios:
        directorios = []

    try:
        validar_solicitud(
            tipo=tipo,
            objetos=objetos,
            directorio=directorio,
            nombre=nombre,
            objetos_disponibles=disponibles,
            directorios_disponibles=[d.nombre for d in directorios],
        )
    except SolicitudInvalida as error:
        return JSONResponse(status_code=422, content={"errores": error.errores})

    ruta = next(d.ruta for d in directorios if d.nombre == directorio)
    try:
        resultado = respaldar(
            tipo=tipo,
            conexion=conexion,
            objetos=objetos,
            directorio=directorio,
            nombre=nombre,
            contenedor=os.environ.get("ORACLE_CONTAINER", "oracle21c"),
            ejecutar=ejecutar,
            ahora=datetime.now(),
            ruta_directorio=ruta,
        )
    except RespaldoFallido as error:
        return JSONResponse(
            status_code=500,
            content={
                "mensaje": str(error),
                "explicacion": error.explicacion,
                "log": error.log,
            },
        )
    return {"dmp": resultado.dmp, "log": resultado.log}


@router.get("/tablas")
def get_tablas(consulta=Depends(obtener_consulta)):
    return _listado("tablas", listar_tablas, SinTablas, consulta)


@router.get("/schemas")
def get_schemas(consulta=Depends(obtener_consulta)):
    return _listado("schemas", listar_schemas, SinSchemas, consulta)


@router.get("/directorios")
def get_directorios(consulta=Depends(obtener_consulta)):
    try:
        directorios = listar_directorios(consulta)
    except SinDirectorios as error:
        raise HTTPException(status_code=404, detail=str(error))
    return {"directorios": [{"nombre": d.nombre, "ruta": d.ruta} for d in directorios]}


@router.post("/tablas")
def post_tablas(
    solicitud: SolicitudRespaldo,
    conexion: Conexion = Depends(obtener_conexion),
    consulta=Depends(obtener_consulta),
    ejecutar=Depends(obtener_ejecutor),
):
    return _respaldo(
        TABLAS, listar_tablas, SinTablas, solicitud.tablas, solicitud.directorio,
        solicitud.nombre, conexion, consulta, ejecutar,
    )


@router.post("/schemas")
def post_schemas(
    solicitud: SolicitudRespaldoSchemas,
    conexion: Conexion = Depends(obtener_conexion),
    consulta=Depends(obtener_consulta),
    ejecutar=Depends(obtener_ejecutor),
):
    return _respaldo(
        SCHEMAS, listar_schemas, SinSchemas, solicitud.schemas, solicitud.directorio,
        solicitud.nombre, conexion, consulta, ejecutar,
    )
