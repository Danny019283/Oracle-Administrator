from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.admin_comun import exigir_sysdba_o_dba, obtener_consulta_admin, obtener_sentencia, responder
from src.api.dependencias import obtener_conexion, obtener_entorno
from src.api.sesion import obtener_almacen
from src.services import directorios
from src.services.archivos_respaldo import eliminar_respaldo, listar_respaldos
from src.api.respaldos import respuesta_herramienta_no_disponible
from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida
from src.services.errores_oracle import explicacion_de
from src.services.instancia import sid_de_instancia
from src.services.recuperacion import RecuperacionFallida, recuperar_datapump, recuperar_full, recuperar_tabla
from src.services.respaldo_full import SinArchivelog

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


@router.get("/respaldos", dependencies=[Depends(exigir_sysdba_o_dba)])
def get_respaldos(consulta=Depends(obtener_consulta_admin), entorno=Depends(obtener_entorno)):
    def listar():
        respaldos, avisos = listar_respaldos(consulta, entorno)
        return {
            "respaldos": [
                {
                    "directorio": r.directorio,
                    "ruta": r.ruta,
                    "base": r.base,
                    "tipo": r.tipo,
                    "estado": r.estado,
                    "archivos": [{"nombre": a.nombre, "tamano": a.tamano} for a in r.archivos],
                    "tamano": r.tamano,
                    "fecha": r.fecha.isoformat(),
                }
                for r in respaldos
            ],
            "avisos": avisos,
        }

    return responder(listar)


@router.delete("/{nombre}/respaldos/{base}", dependencies=[Depends(exigir_sysdba_o_dba)])
def delete_respaldo(
    nombre: str,
    base: str,
    consulta=Depends(obtener_consulta_admin),
    entorno=Depends(obtener_entorno),
):
    def eliminar():
        try:
            resultado = eliminar_respaldo(consulta, entorno, nombre, base, sid_de_instancia(consulta))
        except OperacionEntornoFallida as error:
            return JSONResponse(
                status_code=500,
                content={
                    "mensaje": "No se pudo eliminar el respaldo",
                    "explicacion": "El archivo puede estar en uso, ser de solo lectura o el usuario no tiene permiso para borrarlo.",
                    "error": str(error).strip(),
                },
            )
        advertencia = resultado.advertencia
        return {
            "mensaje": f"Respaldo {base} eliminado",
            "advertencia": None
            if advertencia is None
            else {"explicacion": advertencia.explicacion, "log": advertencia.log},
        }

    return responder(eliminar)


class SolicitudDatapump(BaseModel):
    modo: Literal["datapump"]
    objeto_modo: str
    objetos: list[str]
    existentes: str = "SKIP"


class SolicitudFull(BaseModel):
    modo: Literal["full"]
    hasta: str | None = None


class SolicitudTabla(BaseModel):
    modo: Literal["tabla"]
    tabla: str
    hasta: str
    nuevo_nombre: str


SolicitudRecuperar = Annotated[SolicitudDatapump | SolicitudFull | SolicitudTabla, Field(discriminator="modo")]


@router.post("/{nombre}/respaldos/{base}/recuperar")
def post_recuperar(
    nombre: str,
    base: str,
    solicitud: SolicitudRecuperar,
    conexion=Depends(obtener_conexion),
    consulta=Depends(obtener_consulta_admin),
    entorno=Depends(obtener_entorno),
    almacen=Depends(obtener_almacen),
):
    # el permiso depende del modo del cuerpo, por eso se decide aquí y no como dependencia de la ruta
    if solicitud.modo == "datapump":
        exigir_sysdba_o_dba(conexion, consulta)
    elif not conexion.sysdba:
        raise HTTPException(status_code=403, detail="Se requiere sesión SYSDBA")

    def recuperar():
        ahora = datetime.now()
        respuesta = {"mensaje": f"Respaldo {base} recuperado"}
        if solicitud.modo == "datapump":
            resultado = recuperar_datapump(
                consulta, entorno, conexion, nombre, base, solicitud.objeto_modo, solicitud.objetos,
                solicitud.existentes, ahora,
            )
        elif solicitud.modo == "tabla":
            resultado = recuperar_tabla(
                consulta, entorno, nombre, base, solicitud.tabla, solicitud.hasta, solicitud.nuevo_nombre,
                sid_de_instancia(consulta), ahora,
            )
        else:
            try:
                resultado = recuperar_full(
                    consulta, entorno, nombre, base, solicitud.hasta, sid_de_instancia(consulta), ahora
                )
            except RecuperacionFallida:
                almacen.cerrar_todas()  # RMAN llegó a apagar la base: las sesiones ya no valen
                raise
            almacen.cerrar_todas()
            respuesta["sesion_cerrada"] = True
        return {**respuesta, "log": resultado.log, "advertencia": resultado.advertencia}

    def con_errores_de_recuperacion():
        try:
            return recuperar()
        except RecuperacionFallida as error:
            return JSONResponse(
                status_code=500,
                content={"mensaje": "No se pudo recuperar el respaldo", "explicacion": error.explicacion, "log": error.log},
            )
        except SinArchivelog as error:
            return JSONResponse(
                status_code=409,
                content={"mensaje": str(error), "explicacion": explicacion_de("RMAN-06149")},
            )
        except HerramientaNoDisponible as error:
            return respuesta_herramienta_no_disponible(error)
        except OperacionEntornoFallida as error:
            return JSONResponse(
                status_code=500,
                content={
                    "mensaje": "No se pudo preparar o limpiar la carpeta auxiliar de la recuperación",
                    "explicacion": "Oracle necesita escribir en la carpeta aux_<base> junto al respaldo y poder borrarla; revisa los permisos de la carpeta del DIRECTORY.",
                    "error": str(error).strip(),
                },
            )

    return responder(con_errores_de_recuperacion)


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
