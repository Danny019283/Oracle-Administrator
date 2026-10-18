import pytest

from src.services.respaldo_schemas import SolicitudInvalida, validar_solicitud_schemas

SCHEMAS = ["HR", "VENTAS"]
DIRECTORIOS = ["RESPALDO", "DATA_PUMP_DIR"]


def validar(schemas=("HR",), directorio="RESPALDO", nombre="ventas"):
    return validar_solicitud_schemas(
        schemas=list(schemas),
        directorio=directorio,
        nombre=nombre,
        schemas_disponibles=SCHEMAS,
        directorios_disponibles=DIRECTORIOS,
    )


def errores_de(**kwargs):
    with pytest.raises(SolicitudInvalida) as error:
        validar(**kwargs)
    return error.value.errores


def test_una_solicitud_completa_es_valida():
    validar(schemas=("HR", "VENTAS"))


def test_exige_al_menos_un_schema():
    assert errores_de(schemas=()) == ["Debes seleccionar al menos un schema"]


def test_exige_directorio():
    assert errores_de(directorio="") == ["Debes elegir un directorio"]


def test_exige_nombre_de_dumpfile():
    assert errores_de(nombre="") == ["Debes ingresar un nombre de dumpfile"]


def test_informa_todos_los_datos_faltantes_juntos():
    assert errores_de(schemas=(), directorio="", nombre="") == [
        "Debes seleccionar al menos un schema",
        "Debes elegir un directorio",
        "Debes ingresar un nombre de dumpfile",
    ]


def test_rechaza_nombre_invalido_junto_con_los_demas_errores():
    errores = errores_de(schemas=(), nombre="a b")

    assert errores[0] == "Debes seleccionar al menos un schema"
    assert len(errores) == 2
    assert "nombre" in errores[1].lower()


def test_rechaza_directorio_que_no_esta_disponible():
    assert errores_de(directorio="OTRO") == ["El directorio OTRO no está disponible"]


def test_rechaza_schemas_que_no_son_de_usuario():
    assert errores_de(schemas=("HR", "SYS")) == [
        "El schema SYS no es un schema de usuario disponible"
    ]
