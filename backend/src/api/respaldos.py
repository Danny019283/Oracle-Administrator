import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services.directorios import SinDirectorios, listar_directorios
from src.services.docker_ejecutor import ejecutar_docker
from src.services.expdp_runner import Conexion
from src.services.oracle_conexion import consulta_oracle
from src.services.respaldo_schemas import respaldar_schemas, validar_solicitud_schemas
from src.services.respaldo_tablas import (
    RespaldoFallido,
    SolicitudInvalida,
    respaldar_tablas,
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


@router.get("/tablas")
def get_tablas(consulta=Depends(obtener_consulta)):
    try:
        return {"tablas": listar_tablas(consulta)}
    except SinTablas as error:
        raise HTTPException(status_code=404, detail=str(error))


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
    try:
        tablas_disponibles = listar_tablas(consulta)
    except SinTablas:
        tablas_disponibles = []
    try:
        directorios = listar_directorios(consulta)
    except SinDirectorios:
        directorios = []

    try:
        validar_solicitud(
            tablas=solicitud.tablas,
            directorio=solicitud.directorio,
            nombre=solicitud.nombre,
            tablas_disponibles=tablas_disponibles,
            directorios_disponibles=[d.nombre for d in directorios],
        )
    except SolicitudInvalida as error:
        return JSONResponse(status_code=422, content={"errores": error.errores})

    ruta = next(d.ruta for d in directorios if d.nombre == solicitud.directorio)
    try:
        resultado = respaldar_tablas(
            conexion=conexion,
            tablas=solicitud.tablas,
            directorio=solicitud.directorio,
            nombre=solicitud.nombre,
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


class SolicitudRespaldoSchemas(BaseModel):
    schemas: list[str] = []
    directorio: str = ""
    nombre: str = ""


@router.get("/schemas")
def get_schemas(consulta=Depends(obtener_consulta)):
    try:
        return {"schemas": listar_schemas(consulta)}
    except SinSchemas as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/schemas")
def post_schemas(
    solicitud: SolicitudRespaldoSchemas,
    conexion: Conexion = Depends(obtener_conexion),
    consulta=Depends(obtener_consulta),
    ejecutar=Depends(obtener_ejecutor),
):
    try:
        schemas_disponibles = listar_schemas(consulta)
    except SinSchemas:
        schemas_disponibles = []
    try:
        directorios = listar_directorios(consulta)
    except SinDirectorios:
        directorios = []

    try:
        validar_solicitud_schemas(
            schemas=solicitud.schemas,
            directorio=solicitud.directorio,
            nombre=solicitud.nombre,
            schemas_disponibles=schemas_disponibles,
            directorios_disponibles=[d.nombre for d in directorios],
        )
    except SolicitudInvalida as error:
        return JSONResponse(status_code=422, content={"errores": error.errores})

    ruta = next(d.ruta for d in directorios if d.nombre == solicitud.directorio)
    try:
        resultado = respaldar_schemas(
            conexion=conexion,
            schemas=solicitud.schemas,
            directorio=solicitud.directorio,
            nombre=solicitud.nombre,
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
