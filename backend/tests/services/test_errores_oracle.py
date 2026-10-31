import pytest

from src.services.errores_oracle import EXPLICACION_GENERICA, explicar_error


@pytest.mark.parametrize(
    "log, esperado",
    [
        (
            "ORA-39001: argumento no válido\n"
            "ORA-31641: no se puede crear el archivo de volcado\n"
            "ORA-27038: el archivo creado ya existe",
            "Ya existe un archivo de respaldo con ese nombre en el directorio",
        ),
        (
            "ORA-39002: operación no válida\nORA-39087: el nombre de directorio RESPALDO no es válido",
            "El nombre del DIRECTORY no es válido o no existe en Oracle",
        ),
        (
            "ORA-39002: operación no válida\nORA-39070: no se puede abrir el archivo de log",
            "No se puede abrir el archivo de log: revisa los permisos del DIRECTORY",
        ),
        (
            "ORA-39166: no se ha encontrado el objeto HR.XYZ",
            "Alguna de las tablas seleccionadas no existe en el schema",
        ),
        (
            "ORA-01017: usuario/contraseña no válidos; conexión denegada",
            "Usuario o contraseña de Oracle incorrectos",
        ),
        (
            "ORA-12514: el listener no reconoce el servicio solicitado",
            "El servicio de Oracle indicado no existe",
        ),
        (
            "ORA-39002: operación no válida",
            "La operación no es válida; revisa el DIRECTORY y los permisos",
        ),
    ],
)
def test_explica_en_lenguaje_natural_el_codigo_ora_conocido(log, esperado):
    assert explicar_error(log) == esperado


def test_un_codigo_ora_conocido_prevalece_sobre_el_generico_39002_sin_importar_el_orden():
    log = "ORA-39070: no se puede abrir el archivo de log\nORA-39002: operación no válida"

    assert explicar_error(log).startswith("No se puede abrir el archivo de log")


def test_un_codigo_ora_desconocido_da_la_explicacion_generica():
    assert explicar_error("ORA-99999: error raro") == EXPLICACION_GENERICA
    assert EXPLICACION_GENERICA == (
        "Oracle devolvió un error que no está catalogado; revisa el error y el log"
    )


def test_un_log_sin_codigo_ora_da_la_explicacion_generica():
    assert explicar_error("") == EXPLICACION_GENERICA
    assert explicar_error("expdp: command not found") == EXPLICACION_GENERICA


@pytest.mark.parametrize(
    "log, esperado",
    [
        (
            "RMAN-06149: no se puede hacer BACKUP DATABASE en modo NOARCHIVELOG",
            "La base no está en ARCHIVELOG: actívalo para respaldar en caliente",
        ),
        (
            "RMAN-06059: no se encuentra el archivelog esperado",
            "Faltan archivelogs necesarios para el respaldo; ejecuta un CROSSCHECK",
        ),
        (
            "ORA-19809: se ha superado el límite de los archivos de recuperación",
            "Se superó el límite de la zona de recuperación (FRA)",
        ),
        (
            "ORA-19504: fallo al crear el archivo",
            "No se pudo crear el archivo de respaldo; revisa el DIRECTORY y sus permisos",
        ),
        (
            "RMAN-03002: fallo del comando backup",
            "RMAN falló al ejecutar el respaldo; revisa el log",
        ),
    ],
)
def test_explica_en_lenguaje_natural_el_codigo_rman_conocido(log, esperado):
    assert explicar_error(log) == esperado


def test_un_codigo_rman_especifico_prevalece_sobre_el_envoltorio_03002():
    log = (
        "RMAN-00569: =====PILA DE MENSAJES DE ERROR=====\n"
        "RMAN-03002: fallo del comando backup\n"
        "RMAN-06149: no se puede hacer BACKUP DATABASE en modo NOARCHIVELOG"
    )

    assert explicar_error(log).startswith("La base no está en ARCHIVELOG")


@pytest.mark.parametrize(
    "log, esperado",
    [
        (
            "ORA-39151: la tabla \"HR\".\"EMP\" existe. Se omitirán los datos",
            "La tabla ya existe y se omitió; elige Agregar, Vaciar o Reemplazar si quieres cargar sus datos",
        ),
        (
            "ORA-39083: el tipo de objeto INDEX no se pudo crear con el error",
            "Falló la creación de un objeto durante la importación; revisa el log",
        ),
        (
            "ORA-31684: el tipo de objeto USER ya existe",
            "El objeto ya existe en la base de destino",
        ),
        (
            "ORA-31655: no se han seleccionado objetos de datos o metadatos para el trabajo",
            "No se seleccionó ningún objeto para importar; revisa los nombres de tablas o schemas",
        ),
        (
            "ORA-39111: se omite el tipo de objeto dependiente INDEX, el objeto base ya existe",
            "Se omitió un objeto dependiente porque su objeto base ya existe",
        ),
        (
            "ORA-31626: el trabajo no existe",
            "El trabajo de Data Pump no existe o ya terminó",
        ),
        (
            "RMAN-06023: no hay copia de seguridad ni copia del archivo de datos 1 para restaurar",
            "No hay una copia del datafile para restaurar en este respaldo",
        ),
        (
            "RMAN-06026: no se han encontrado algunos destinos; se cancela la restauración",
            "Algunos destinos no se encontraron en el respaldo; no se pudo restaurar",
        ),
        (
            "RMAN-06054: la recuperación de medios solicita el archive log secuencia 12",
            "La recuperación pide un archive log que no se encuentra; ejecuta un CROSSCHECK o usa un UNTIL TIME anterior",
        ),
        (
            "ORA-01139: la opción RESETLOGS solo es válida tras una recuperación incompleta",
            "RESETLOGS solo es válido tras una recuperación incompleta; recupera sin RESETLOGS o indica UNTIL TIME",
        ),
    ],
)
def test_explica_los_codigos_de_la_recuperacion(log, esperado):
    assert explicar_error(log) == esperado


def test_un_codigo_de_recuperacion_prevalece_sobre_los_envoltorios_en_un_log_real():
    log = (
        "ORA-39002: operación no válida\n"
        "ORA-39151: la tabla \"HR\".\"EMP\" existe\n"
        "RMAN-03002: fallo del comando recover\n"
        "RMAN-06054: la recuperación de medios solicita el archive log"
    )

    assert explicar_error(log).startswith("La tabla ya existe y se omitió")


def test_ora_01139_prevalece_sobre_el_envoltorio_rman_03002():
    log = (
        "RMAN-03002: fallo del comando alter db\n"
        "ORA-01139: la opción RESETLOGS solo es válida tras una recuperación incompleta"
    )

    assert explicar_error(log).startswith("RESETLOGS solo es válido")
