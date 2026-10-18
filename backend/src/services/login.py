import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import oracledb

from src.services.errores_oracle import explicacion_de
from src.services.expdp_runner import Conexion
from src.services.respaldo import SolicitudInvalida
from src.services.sesiones import AlmacenSesiones

__all__ = [
    "LoginFallido",
    "SesionIniciada",
    "SolicitudInvalida",
    "SolicitudLogin",
    "conectar_oracle",
    "iniciar_sesion",
    "validar_login",
]

PUERTO_MAXIMO = 65535

_CODIGO = re.compile(r"ORA-\d{5}|DPY-\d{4}")
_INALCANZABLES = {"ORA-12541", "ORA-12514", "DPY-6005"}
_MENSAJE_GENERICO = "No se pudo iniciar sesión"
# Por red Oracle responde ORA-01017 tanto a credenciales inválidas como a un usuario sin SYSDBA.
_MENSAJE_SYSDBA_SIN_PRIVILEGIO = (
    "Usuario o contraseña de Oracle incorrectos, o el usuario no tiene privilegio SYSDBA"
)


@dataclass(frozen=True)
class SolicitudLogin:
    host: str
    puerto: int
    servicio: str
    usuario: str
    password: str
    sysdba: bool = False


@dataclass(frozen=True)
class SesionIniciada:
    token: str
    usuario: str
    sysdba: bool


class LoginFallido(Exception):
    def __init__(self, mensaje: str, codigo: str | None, inalcanzable: bool):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.inalcanzable = inalcanzable


def validar_login(
    host: str,
    puerto: int | str,
    servicio: str,
    usuario: str,
    password: str,
    sysdba: bool = False,
) -> SolicitudLogin:
    errores: list[str] = []
    textos = {
        "host": host.strip(),
        "servicio": servicio.strip(),
        "usuario": usuario.strip(),
    }
    for campo, valor in textos.items():
        if not valor:
            errores.append(f"El campo {campo} es obligatorio")
    if not password.strip():
        errores.append("El campo password es obligatorio")

    texto_puerto = str(puerto).strip()
    numero = None
    if not texto_puerto:
        errores.append("El campo puerto es obligatorio")
    elif not (texto_puerto.isascii() and texto_puerto.isdigit()):
        errores.append("El puerto debe ser un número")
    elif not 1 <= int(texto_puerto) <= PUERTO_MAXIMO:
        errores.append(f"El puerto debe estar entre 1 y {PUERTO_MAXIMO}")
    else:
        numero = int(texto_puerto)

    if errores:
        raise SolicitudInvalida(errores)
    return SolicitudLogin(
        host=textos["host"],
        puerto=numero,
        servicio=textos["servicio"],
        usuario=textos["usuario"],
        password=password,
        sysdba=sysdba,
    )


def conectar_oracle(pedido: SolicitudLogin, driver: Any = oracledb) -> None:
    modo = driver.AUTH_MODE_SYSDBA if pedido.sysdba else driver.AUTH_MODE_DEFAULT
    conexion = driver.connect(
        user=pedido.usuario,
        password=pedido.password,
        dsn=f"{pedido.host}:{pedido.puerto}/{pedido.servicio}",
        mode=modo,
    )
    conexion.close()


def _traducir(error: Exception, sysdba: bool) -> LoginFallido:
    encontrado = _CODIGO.search(str(error))
    codigo = encontrado.group() if encontrado else None
    if codigo is None:
        return LoginFallido(_MENSAJE_GENERICO, None, False)
    if sysdba and codigo == "ORA-01017":
        return LoginFallido(f"{_MENSAJE_SYSDBA_SIN_PRIVILEGIO} ({codigo})", codigo, False)
    explicacion = explicacion_de(codigo) or _MENSAJE_GENERICO
    return LoginFallido(f"{explicacion} ({codigo})", codigo, codigo in _INALCANZABLES)


def iniciar_sesion(
    pedido: SolicitudLogin,
    almacen: AlmacenSesiones,
    conectar: Callable[[SolicitudLogin], None] = conectar_oracle,
) -> SesionIniciada:
    try:
        conectar(pedido)
    except Exception as error:
        raise _traducir(error, pedido.sysdba) from None
    token = almacen.crear(
        Conexion(
            usuario=pedido.usuario,
            password=pedido.password,
            servicio=pedido.servicio,
            host=pedido.host,
            puerto=pedido.puerto,
            sysdba=pedido.sysdba,
        )
    )
    return SesionIniciada(token=token, usuario=pedido.usuario, sysdba=pedido.sysdba)
