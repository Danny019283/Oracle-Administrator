from dataclasses import dataclass

from src.services.respaldo import SolicitudInvalida

__all__ = ["SolicitudInvalida", "SolicitudLogin", "validar_login"]

PUERTO_MAXIMO = 65535


@dataclass(frozen=True)
class SolicitudLogin:
    host: str
    puerto: int
    servicio: str
    usuario: str
    password: str
    sysdba: bool = False


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
