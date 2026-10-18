import re

EXPLICACION_GENERICA = (
    "Oracle devolvió un error que no está catalogado; revisa el error y el log"
)

_EXPLICACIONES = {
    "ORA-27038": "Ya existe un archivo de respaldo con ese nombre en el directorio",
    "ORA-39087": "El nombre del DIRECTORY no es válido o no existe en Oracle",
    "ORA-39070": "No se puede abrir el archivo de log: revisa los permisos del DIRECTORY",
    "ORA-39166": "Alguna de las tablas seleccionadas no existe en el schema",
    "ORA-01017": "Usuario o contraseña de Oracle incorrectos",
    "ORA-12514": "El servicio de Oracle indicado no existe",
    "ORA-39002": "La operación no es válida; revisa el DIRECTORY y los permisos",
    "ORA-12541": "No hay un listener de Oracle escuchando en ese host y puerto",
    "ORA-01031": "El usuario no tiene el privilegio necesario (¿SYSDBA?)",
    "ORA-28000": "La cuenta de Oracle está bloqueada",
    "ORA-28001": "La contraseña de Oracle ha expirado",
    "DPY-6005": "No se pudo alcanzar el servidor de Oracle en ese host y puerto",
}

# Oracle envuelve casi todos los fallos de Data Pump con este código; solo
# explica cuando no hay otro más específico.
_ENVOLTORIO = "ORA-39002"


def explicacion_de(codigo: str) -> str | None:
    return _EXPLICACIONES.get(codigo)


def explicar_error(log: str) -> str:
    codigos = re.findall(r"ORA-\d{5}", log)
    for codigo in codigos:
        if codigo != _ENVOLTORIO and codigo in _EXPLICACIONES:
            return _EXPLICACIONES[codigo]
    if _ENVOLTORIO in codigos:
        return _EXPLICACIONES[_ENVOLTORIO]
    return EXPLICACION_GENERICA
