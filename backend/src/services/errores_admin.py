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
    "ORA-01543": "Ya existe un tablespace con ese nombre",
    "ORA-27038": "Ya existe un archivo con ese nombre en el servidor; elige otro nombre",
    "ORA-01119": "Oracle no pudo crear el archivo de datos; revisa el nombre y el espacio libre en disco",
    "ORA-01537": "Ese archivo ya forma parte de la base de datos",
    "ORA-03297": "No se puede reducir el archivo a ese tamaño porque tiene datos más allá de ese punto; elige un tamaño mayor",
    "ORA-01516": "El archivo de datos no existe",
    "ORA-01541": "El tablespace SYSTEM no se puede poner OFFLINE",
    "ORA-01643": "El tablespace SYSTEM no se puede poner en solo lectura",
    "ORA-01644": "El tablespace ya está en solo lectura (READ ONLY)",
    "ORA-01646": "El tablespace no está en solo lectura, ya admite escrituras",
    "ORA-01539": "El tablespace no está ONLINE; ponlo ONLINE primero",
    "ORA-30042": "No se puede poner OFFLINE el tablespace de UNDO",
    "ORA-01652": "El tablespace temporal se quedó sin espacio; agrega un archivo o activa AUTOEXTEND",
    "ORA-01653": "El tablespace se quedó sin espacio; agrega un datafile, redimensiónalo o activa AUTOEXTEND",
    "ORA-01654": "El tablespace se quedó sin espacio para el índice; agrega un datafile o activa AUTOEXTEND",
    "ORA-00955": "Ya existe un objeto con ese nombre en el schema; elige otro nombre para el índice",
    "ORA-01408": "Ya existe un índice sobre esas mismas columnas",
    "ORA-01418": "El índice no existe",
    "ORA-02429": "No se puede eliminar un índice que respalda una llave primaria o única",
    "ORA-01452": "No se puede crear el índice único porque la tabla tiene valores repetidos en esas columnas",
    "ORA-00900": "La sentencia SQL no es válida",
    "ORA-00904": "La consulta usa una columna o identificador que no existe",
    "ORA-00933": "La sentencia SQL no terminó correctamente; revisa la sintaxis cerca del final",
    "ORA-00936": "Falta una expresión en la consulta; revisa la sintaxis",
    "ORA-20000": "No se pudieron generar las estadísticas: el objeto no existe o el usuario no tiene privilegios suficientes",
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
