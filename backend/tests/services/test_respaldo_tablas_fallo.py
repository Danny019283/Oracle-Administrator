from datetime import datetime
from pathlib import PurePosixPath

import pytest

from src.services.expdp_runner import Conexion
from src.services.respaldo_tablas import RespaldoFallido, respaldar_tablas
from tests.services.entorno_falso import EntornoFalso

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"
LOG = "ventas_20261017_153045.log"
ERROR_DUPLICADO = (
    "ORA-39001: argumento no válido\n"
    "ORA-31641: no se puede crear el archivo de volcado\n"
    "ORA-27038: el archivo creado ya existe"
)


def entorno_fallido(texto="ORA-39002: operación no válida", log=ERROR_DUPLICADO):
    return EntornoFalso(codigo=5, texto=texto, log=log)


def respaldar(entorno, ruta_directorio=RUTA):
    return respaldar_tablas(
        conexion=CONEXION,
        tablas=["CLIENTES"],
        directorio="RESPALDO",
        nombre="ventas",
        entorno=entorno,
        ahora=AHORA,
        ruta_directorio=ruta_directorio,
    )


def fallo_de(entorno):
    with pytest.raises(RespaldoFallido) as error:
        respaldar(entorno)
    return error.value


def test_si_expdp_falla_informa_el_error_con_el_contenido_del_log():
    fallo = fallo_de(entorno_fallido())

    assert fallo.log == ERROR_DUPLICADO
    assert "ORA-27038" in fallo.log


def test_lee_el_log_del_directorio_a_traves_del_entorno():
    entorno = entorno_fallido()

    fallo_de(entorno)

    assert entorno.lecturas == [PurePosixPath(RUTA) / LOG]


def test_el_mensaje_del_fallo_no_incluye_la_contrasena():
    fallo = fallo_de(entorno_fallido())

    assert "s3creta!" not in str(fallo)
    assert "s3creta!" not in fallo.log


def test_si_no_hay_ruta_del_directorio_informa_la_salida_de_expdp():
    entorno = entorno_fallido()

    with pytest.raises(RespaldoFallido) as error:
        respaldar(entorno, ruta_directorio=None)

    assert error.value.log == "ORA-39002: operación no válida"
    assert entorno.lecturas == []
