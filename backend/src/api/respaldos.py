import os
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.dependencias import obtener_conexion, obtener_entorno
from src.services.archivelog import FRA_DIRECTORIO, ArchivelogFallido, activar_archivelog
from src.services.directorios import SinDirectorios, listar_directorios
from src.services.docker_ejecutor import ejecutar_docker
from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_oracle import EntornoOracle
from src.services.errores_oracle import explicacion_de
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
from src.services.respaldo_full import SinArchivelog, en_archivelog, respaldar_full
from src.services.schemas import SinSchemas, listar_schemas
from src.services.tablas import SinTablas, listar_tablas

router = APIRouter(prefix="/respaldos")


def obtener_consulta(conexion: Conexion = Depends(obtener_conexion)):
    return consulta_oracle(conexion)


def obtener_ejecutor():
    return ejecutar_docker


def exigir_sysdba(conexion: Conexion = Depends(obtener_conexion)) -> Conexion:
    if not conexion.sysdba:
        raise HTTPException(status_code=403, detail="Se requiere sesión SYSDBA")
    return conexion


def _contenedor() -> str:
    return os.environ.get("ORACLE_CONTAINER", "oracle21c")


class SolicitudRespaldo(BaseModel):
    tablas: list[str] = []
    directorio: str = ""
    nombre: str = ""


class SolicitudRespaldoFull(BaseModel):
    directorio: str = ""
    nombre: str = ""


class SolicitudRespaldoSchemas(BaseModel):
    schemas: list[str] = []
    directorio: str = ""
    nombre: str = ""


def respuesta_solicitud_invalida(error: SolicitudInvalida) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errores": error.errores})


def respuesta_respaldo_fallido(error: RespaldoFallido) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "mensaje": str(error),
            "explicacion": error.explicacion,
            "log": error.log,
        },
    )


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
    entorno: EntornoOracle,
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
        return respuesta_solicitud_invalida(error)

    ruta = next(d.ruta for d in directorios if d.nombre == directorio)
    try:
        resultado = respaldar(
            tipo=tipo,
            conexion=conexion,
            objetos=objetos,
            directorio=directorio,
            nombre=nombre,
            entorno=entorno,
            ahora=datetime.now(),
            ruta_directorio=ruta,
        )
    except RespaldoFallido as error:
        return respuesta_respaldo_fallido(error)
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
    entorno=Depends(obtener_entorno),
):
    return _respaldo(
        TABLAS, listar_tablas, SinTablas, solicitud.tablas, solicitud.directorio,
        solicitud.nombre, conexion, consulta, entorno,
    )


@router.post("/schemas")
def post_schemas(
    solicitud: SolicitudRespaldoSchemas,
    conexion: Conexion = Depends(obtener_conexion),
    consulta=Depends(obtener_consulta),
    entorno=Depends(obtener_entorno),
):
    return _respaldo(
        SCHEMAS, listar_schemas, SinSchemas, solicitud.schemas, solicitud.directorio,
        solicitud.nombre, conexion, consulta, entorno,
    )


@router.get("/full/estado")
def get_estado_full(
    _: Conexion = Depends(exigir_sysdba), consulta=Depends(obtener_consulta)
):
    return {"archivelog": en_archivelog(consulta)}


@router.post("/full")
def post_full(
    solicitud: SolicitudRespaldoFull,
    _: Conexion = Depends(exigir_sysdba),
    consulta=Depends(obtener_consulta),
    ejecutar=Depends(obtener_ejecutor),
):
    try:
        directorios = listar_directorios(consulta)
    except SinDirectorios:
        directorios = []

    try:
        resultado = respaldar_full(
            consulta=consulta,
            directorios=directorios,
            directorio=solicitud.directorio,
            nombre=solicitud.nombre,
            entorno=EntornoContenedor(_contenedor(), ejecutar),  # transitorio hasta el check 17
        )
    except SolicitudInvalida as error:
        return respuesta_solicitud_invalida(error)
    except SinArchivelog as error:
        return JSONResponse(
            status_code=409,
            content={"mensaje": str(error), "explicacion": explicacion_de("RMAN-06149")},
        )
    except RespaldoFallido as error:
        return respuesta_respaldo_fallido(error)

    advertencia = resultado.advertencia
    return {
        "log": resultado.log,
        "advertencia": None
        if advertencia is None
        else {"explicacion": advertencia.explicacion, "log": advertencia.log},
    }


@router.post("/full/archivelog")
def post_archivelog(
    _: Conexion = Depends(exigir_sysdba), ejecutar=Depends(obtener_ejecutor)
):
    try:
        # transitorio hasta el check 17
        log = activar_archivelog(EntornoContenedor(_contenedor(), ejecutar), FRA_DIRECTORIO)
    except ArchivelogFallido as error:
        return JSONResponse(
            status_code=500,
            content={
                "mensaje": str(error),
                "explicacion": error.explicacion,
                "log": error.log,
            },
        )
    return {"mensaje": "ARCHIVELOG activado. Inicia sesión de nuevo", "log": log}
