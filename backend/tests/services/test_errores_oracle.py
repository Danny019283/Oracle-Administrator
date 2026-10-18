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
