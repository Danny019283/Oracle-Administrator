import re

from src.services.errores_oracle import EXPLICACION_GENERICA, explicar_error

_EXPLICACIONES = {
    "ORA-01031": "El usuario conectado no tiene privilegios suficientes para esta operación; usa un usuario administrador como SYSTEM",
    "ORA-00942": "La vista o tabla no existe o el usuario conectado no tiene permiso para consultarla (para la auditoría se necesita el rol AUDIT_VIEWER o AUDIT_ADMIN)",
    "ORA-01920": "Ya existe un usuario o un rol con ese nombre",
    "ORA-01918": "El usuario no existe",
    "ORA-01919": "El rol no existe",
    "ORA-65096": "En el contenedor raíz (CDB) los usuarios deben empezar con C##; conéctate al servicio XEPDB1 para crear usuarios normales",
    "ORA-00959": "El tablespace indicado no existe",
    "ORA-01940": "No se puede eliminar un usuario que tiene sesiones abiertas; ciérralas primero desde Performance",
    "ORA-28003": "La contraseña no cumple con la política de contraseñas del perfil del usuario",
    "ORA-00988": "La contraseña no es válida",
    "ORA-28014": "No se puede eliminar un usuario administrativo de Oracle",
    "ORA-01951": "El usuario no tiene ese rol, no hay nada que revocar",
    "ORA-01952": "El usuario no tiene ese privilegio, no hay nada que revocar",
    "ORA-01927": "No se puede revocar un privilegio que no fue otorgado por este usuario",
    "ORA-00030": "La sesión ya no existe (probablemente ya terminó)",
    "ORA-00027": "No se puede terminar la sesión con la que está conectada la aplicación",
    "ORA-46357": "La política de auditoría no existe",
    "ORA-46358": "Ya existe una política de auditoría con ese nombre",
    "ORA-46361": "No se puede eliminar una política de auditoría habilitada; deshabilítala primero",
    "DPY-6005": "No se pudo conectar con Oracle; verifica que el contenedor oracle21c esté encendido",
}


def codigo_error(mensaje: str) -> str | None:
    encontrado = re.search(r"(ORA|DPY)-\d{4,5}", mensaje)
    return encontrado.group(0) if encontrado else None


def explicar_error_admin(mensaje: str) -> str:
    """Explica en lenguaje natural un error de Oracle o del driver."""
    for codigo in re.findall(r"(?:ORA|DPY)-\d{4,5}", mensaje):
        if codigo in _EXPLICACIONES:
            return _EXPLICACIONES[codigo]
    explicacion = explicar_error(mensaje)
    return explicacion if explicacion != EXPLICACION_GENERICA else EXPLICACION_GENERICA
