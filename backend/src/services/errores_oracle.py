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
    "ORA-28009": "SYS debe conectarse como SYSDBA: marca la casilla «Iniciar como SYSDBA»",
    "RMAN-06149": "La base no está en ARCHIVELOG: actívalo para respaldar en caliente",
    "RMAN-03002": "RMAN falló al ejecutar el respaldo; revisa el log",
    "RMAN-06059": "Faltan archivelogs necesarios para el respaldo; ejecuta un CROSSCHECK",
    "ORA-19809": "Se superó el límite de la zona de recuperación (FRA)",
    "ORA-19504": "No se pudo crear el archivo de respaldo; revisa el DIRECTORY y sus permisos",
    "ORA-39151": "La tabla ya existe y se omitió; elige Agregar, Vaciar o Reemplazar si quieres cargar sus datos",
    "ORA-39083": "Falló la creación de un objeto durante la importación; revisa el log",
    "ORA-31684": "El objeto ya existe en la base de destino",
    "ORA-31655": "No se seleccionó ningún objeto para importar; revisa los nombres de tablas o schemas",
    "ORA-39111": "Se omitió un objeto dependiente porque su objeto base ya existe",
    "ORA-31626": "El trabajo de Data Pump no existe o ya terminó",
    "RMAN-06023": "No hay una copia del datafile para restaurar en este respaldo",
    "RMAN-06026": "Algunos destinos no se encontraron en el respaldo; no se pudo restaurar",
    "RMAN-06054": "La recuperación pide un archive log que no se encuentra; ejecuta un CROSSCHECK o usa un UNTIL TIME anterior",
    "DPY-6005": "No se pudo alcanzar el servidor de Oracle en ese host y puerto",
}

# Oracle envuelve casi todos los fallos de Data Pump (ORA-39002) y de RMAN
# (RMAN-03002) con estos códigos; solo explican cuando no hay otro más específico.
_ENVOLTORIOS = ("ORA-39002", "RMAN-03002")


def explicacion_de(codigo: str) -> str | None:
    return _EXPLICACIONES.get(codigo)


def explicar_error(log: str) -> str:
    codigos = re.findall(r"(?:ORA|RMAN)-\d{5}", log)
    for codigo in codigos:
        if codigo not in _ENVOLTORIOS and codigo in _EXPLICACIONES:
            return _EXPLICACIONES[codigo]
    for envoltorio in _ENVOLTORIOS:
        if envoltorio in codigos:
            return _EXPLICACIONES[envoltorio]
    return EXPLICACION_GENERICA
