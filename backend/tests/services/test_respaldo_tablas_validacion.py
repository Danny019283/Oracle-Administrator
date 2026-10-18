import pytest

from src.services.respaldo_tablas import SolicitudInvalida, validar_solicitud

TABLAS = ["CLIENTES", "PEDIDOS"]
DIRECTORIOS = ["RESPALDO", "DATA_PUMP_DIR"]


def validar(tablas=("CLIENTES",), directorio="RESPALDO", nombre="ventas"):
    return validar_solicitud(
        tablas=list(tablas),
        directorio=directorio,
        nombre=nombre,
        tablas_disponibles=TABLAS,
        directorios_disponibles=DIRECTORIOS,
    )


def errores_de(**kwargs):
    with pytest.raises(SolicitudInvalida) as error:
        validar(**kwargs)
    return error.value.errores


def test_una_solicitud_completa_es_valida():
    validar(tablas=("CLIENTES", "PEDIDOS"))


def test_exige_al_menos_una_tabla():
    errores = errores_de(tablas=())

    assert errores == ["Debes seleccionar al menos una tabla"]


def test_exige_directorio():
    errores = errores_de(directorio="")

    assert errores == ["Debes elegir un directorio"]


def test_exige_nombre_de_dumpfile():
    errores = errores_de(nombre="")

    assert errores == ["Debes ingresar un nombre de dumpfile"]


def test_informa_todos_los_datos_faltantes_juntos():
    errores = errores_de(tablas=(), directorio="", nombre="")

    assert errores == [
        "Debes seleccionar al menos una tabla",
        "Debes elegir un directorio",
        "Debes ingresar un nombre de dumpfile",
    ]


def test_rechaza_nombre_invalido_junto_con_los_demas_errores():
    errores = errores_de(tablas=(), nombre="a b")

    assert errores[0] == "Debes seleccionar al menos una tabla"
    assert len(errores) == 2
    assert "nombre" in errores[1].lower()


def test_rechaza_directorio_que_no_esta_disponible():
    errores = errores_de(directorio="OTRO")

    assert errores == ["El directorio OTRO no está disponible"]


def test_rechaza_tablas_que_no_son_del_usuario():
    errores = errores_de(tablas=("CLIENTES", "SYS.USER$"))

    assert errores == ["La tabla SYS.USER$ no pertenece al schema del usuario"]
