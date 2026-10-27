from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.services import seguridad

router = APIRouter(prefix="/seguridad")


class SolicitudUsuario(BaseModel):
    usuario: str = ""
    password: str = ""
    tablespace: str = ""
    temporal: str = ""
    cuota: str = "UNLIMITED"
    permitir_conexion: bool = True


class SolicitudPassword(BaseModel):
    password: str = ""


class SolicitudConfirmar(BaseModel):
    confirmar: bool = False


class SolicitudPermiso(BaseModel):
    nombre: str = ""
    otorgar: bool = True


@router.get("/usuarios")
def get_usuarios(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: {"usuarios": seguridad.listar_usuarios(consulta)})


@router.get("/catalogos")
def get_catalogos(consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: seguridad.catalogos(consulta))


@router.get("/usuarios/{usuario}")
def get_usuario(usuario: str, consulta=Depends(obtener_consulta_admin)):
    return responder(lambda: seguridad.detalle_usuario(consulta, usuario))


@router.post("/usuarios")
def post_usuario(
    solicitud: SolicitudUsuario,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def crear():
        nombre = seguridad.crear_usuario(
            consulta,
            sentencia,
            usuario=solicitud.usuario,
            password=solicitud.password,
            tablespace=solicitud.tablespace,
            temporal=solicitud.temporal,
            cuota=solicitud.cuota,
            permitir_conexion=solicitud.permitir_conexion,
        )
        return {"mensaje": f"Usuario {nombre} creado"}

    return responder(crear)


@router.post("/usuarios/{usuario}/password")
def post_password(
    usuario: str,
    solicitud: SolicitudPassword,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    return responder(
        lambda: {
            "mensaje": "Contraseña de "
            f"{seguridad.cambiar_password(consulta, sentencia, usuario, solicitud.password)} cambiada"
        }
    )


@router.post("/usuarios/{usuario}/bloquear")
def post_bloquear(
    usuario: str, consulta=Depends(obtener_consulta_admin), sentencia=Depends(obtener_sentencia)
):
    return responder(
        lambda: {"mensaje": f"Usuario {seguridad.bloquear(consulta, sentencia, usuario, True)} bloqueado"}
    )


@router.post("/usuarios/{usuario}/desbloquear")
def post_desbloquear(
    usuario: str, consulta=Depends(obtener_consulta_admin), sentencia=Depends(obtener_sentencia)
):
    return responder(
        lambda: {
            "mensaje": f"Usuario {seguridad.bloquear(consulta, sentencia, usuario, False)} desbloqueado"
        }
    )


@router.post("/usuarios/{usuario}/eliminar")
def post_eliminar(
    usuario: str,
    solicitud: SolicitudConfirmar,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    if not solicitud.confirmar:
        return JSONResponse(
            status_code=422,
            content={"errores": ["Debes confirmar que quieres eliminar el usuario"]},
        )
    return responder(
        lambda: {"mensaje": f"Usuario {seguridad.eliminar_usuario(consulta, sentencia, usuario)} eliminado"}
    )


@router.post("/usuarios/{usuario}/roles")
def post_rol(
    usuario: str,
    solicitud: SolicitudPermiso,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def cambiar():
        nombre = seguridad.cambiar_rol(consulta, sentencia, usuario, solicitud.nombre, solicitud.otorgar)
        accion = "otorgado a" if solicitud.otorgar else "revocado de"
        return {"mensaje": f"Rol {solicitud.nombre.upper()} {accion} {nombre}"}

    return responder(cambiar)


@router.post("/usuarios/{usuario}/privilegios")
def post_privilegio(
    usuario: str,
    solicitud: SolicitudPermiso,
    consulta=Depends(obtener_consulta_admin),
    sentencia=Depends(obtener_sentencia),
):
    def cambiar():
        nombre = seguridad.cambiar_privilegio(
            consulta, sentencia, usuario, solicitud.nombre, solicitud.otorgar
        )
        accion = "otorgado a" if solicitud.otorgar else "revocado de"
        return {"mensaje": f"Privilegio {' '.join(solicitud.nombre.split()).upper()} {accion} {nombre}"}

    return responder(cambiar)
