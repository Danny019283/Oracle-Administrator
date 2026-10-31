import os
import time
from typing import Any

import oracledb
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.admin_comun import obtener_sentencia
from src.api.dependencias import obtener_entorno, obtener_programador
from src.api.respaldos import (
    exigir_sysdba,
    obtener_consulta,
    respuesta_herramienta_no_disponible,
    respuesta_solicitud_invalida,
)
from src.services import respaldos_programados as servicio
from src.services.directorios import SinDirectorios, listar_directorios
from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida
from src.services.errores_admin import explicar_error_admin
from src.services.errores_oracle import explicacion_de
from src.services.instancia import sid_de_instancia
from src.services.politica_respaldo import Programacion
from src.services.respaldo import RespaldoFallido, SolicitudInvalida
from src.services.respaldo_full import SinArchivelog

router = APIRouter(prefix="/respaldos/programados")


class SolicitudProgramacion(BaseModel):
    nombre: str = ""
    directorio: str = ""
    politica: str = ""
    frecuencia: str = ""
    # Any: un valor de tipo raro debe llegar a validar_programacion (422 {errores}), no al 422 {detail} de pydantic
    hora: Any = None
    dia: Any = None
    intervalo_horas: Any = 2


def _fallo(explicacion: str, log: str, mensaje: str = "No se pudo programar el respaldo") -> JSONResponse:
    return JSONResponse(
        status_code=500, content={"mensaje": mensaje, "explicacion": explicacion, "log": log},
    )


def _fallo_de_entorno(error: Exception, mensaje: str) -> JSONResponse:
    texto = str(error).strip()
    return _fallo(explicar_error_admin(texto), texto, mensaje)


def _iso(fecha):
    return fecha.isoformat() if fecha else None


@router.post("")
def post_programar(
    solicitud: SolicitudProgramacion,
    _=Depends(exigir_sysdba),
    consulta=Depends(obtener_consulta),
    sentencia=Depends(obtener_sentencia),
    entorno=Depends(obtener_entorno),
    programador=Depends(obtener_programador),
):
    prog = Programacion(**solicitud.model_dump())
    try:
        directorios = listar_directorios(consulta)
    except SinDirectorios:
        directorios = []
    try:
        creada = servicio.crear(
            consulta, sentencia, directorios, prog, entorno, programador,
            sid_de_instancia(consulta), os.environ.get("ORACLE_ENTORNO", "contenedor"),
        )
    except SolicitudInvalida as error:
        return respuesta_solicitud_invalida(error)
    except SinArchivelog as error:
        return JSONResponse(
            status_code=409,
            content={"mensaje": str(error), "explicacion": explicacion_de("RMAN-06149")},
        )
    except servicio.ProgramacionDuplicada as error:
        return JSONResponse(status_code=409, content={"mensaje": str(error)})
    except RespaldoFallido as error:
        return _fallo(error.explicacion, error.log)
    except (OperacionEntornoFallida, oracledb.Error) as error:
        texto = str(error).strip()
        return _fallo(explicar_error_admin(texto), texto)
    except HerramientaNoDisponible as error:
        return respuesta_herramienta_no_disponible(error)
    return {
        "mensaje": "Respaldo programado",
        "id": creada.id,
        "ruta_script": creada.ruta_script,
        "ruta_rman": creada.ruta_rman,
    }


@router.get("")
def get_programaciones(_=Depends(exigir_sysdba), consulta=Depends(obtener_consulta)):
    return {
        "programaciones": [
            {
                "id": p.id, "nombre": p.nombre, "politica": p.politica, "frecuencia": p.frecuencia,
                "hora": p.hora, "dia": p.dia, "intervalo_horas": p.intervalo_horas,
                "directorio": p.directorio, "ruta_script": p.ruta_script, "ruta_rman": p.ruta_rman,
                "entorno": p.entorno, "tarea": p.tarea, "creado": _iso(p.creado),
                "ultima_ejecucion": _iso(p.ultima_ejecucion), "ultimo_resultado": p.ultimo_resultado,
            }
            for p in servicio.listar(consulta)
        ]
    }


# declarada antes de las rutas con {id} para que no se confunda con ellas
@router.post("/reinstalar")
def post_reinstalar(
    _=Depends(exigir_sysdba),
    consulta=Depends(obtener_consulta),
    entorno=Depends(obtener_entorno),
    programador=Depends(obtener_programador),
):
    try:
        resultado = servicio.reinstalar(consulta, entorno, programador, sid_de_instancia(consulta))
    except oracledb.Error as error:
        return _fallo_de_entorno(error, "No se pudieron reinstalar las tareas")
    n, m = resultado.reinstaladas, len(resultado.fallidas)
    mensaje = f"{n} programación reinstalada" if n == 1 else f"{n} programaciones reinstaladas"
    if m:
        mensaje += f"; {m} falló" if m == 1 else f"; {m} fallaron"
    return {
        "mensaje": mensaje,
        "reinstaladas": n,
        "fallidas": [{"nombre": f.nombre, "mensaje": f.mensaje} for f in resultado.fallidas],
    }


@router.post("/{id}/ejecutar")
def post_ejecutar(
    id: int,
    _=Depends(exigir_sysdba),
    consulta=Depends(obtener_consulta),
    sentencia=Depends(obtener_sentencia),
    entorno=Depends(obtener_entorno),
):
    mensaje_error = "No se pudo ejecutar el respaldo programado"
    try:
        # reloj: acota el log a la ejecución actual
        ejecutada = servicio.ejecutar(consulta, sentencia, entorno, id, reloj=time.time)
    except servicio.ProgramacionNoEncontrada as error:
        raise HTTPException(status_code=404, detail=str(error))
    except servicio.ScriptNoEncontrado as error:
        return JSONResponse(status_code=409, content={"mensaje": str(error), "detail": str(error)})
    except RespaldoFallido as error:
        return _fallo(error.explicacion, error.log, mensaje_error)
    except (OperacionEntornoFallida, oracledb.Error) as error:
        return _fallo_de_entorno(error, mensaje_error)
    except HerramientaNoDisponible as error:
        return respuesta_herramienta_no_disponible(error)
    return {"mensaje": "Respaldo ejecutado", "resultado": ejecutada.resultado, "log": ejecutada.log}


@router.delete("/{id}")
def delete_programacion(
    id: int,
    _=Depends(exigir_sysdba),
    consulta=Depends(obtener_consulta),
    sentencia=Depends(obtener_sentencia),
    entorno=Depends(obtener_entorno),
    programador=Depends(obtener_programador),
):
    try:
        nombre = servicio.eliminar(consulta, sentencia, entorno, programador, id)
    except servicio.ProgramacionNoEncontrada as error:
        raise HTTPException(status_code=404, detail=str(error))
    except (OperacionEntornoFallida, HerramientaNoDisponible, oracledb.Error) as error:
        return _fallo_de_entorno(error, "No se pudo eliminar la programación")
    return {"mensaje": f"Programación {nombre} eliminada"}
