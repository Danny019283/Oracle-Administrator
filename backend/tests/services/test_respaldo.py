from datetime import datetime
from pathlib import PurePosixPath

import pytest

from src.services.expdp_runner import Conexion
from src.services.respaldo import (
    SCHEMAS,
    TABLAS,
    RespaldoFallido,
    leer_log,
    respaldar,
)
from tests.services.entorno_falso import EntornoFalso

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"


def respaldo(tipo, objetos, entorno, ruta_directorio=None):
    return respaldar(
        tipo=tipo,
        conexion=CONEXION,
        objetos=objetos,
        directorio="RESPALDO",
        nombre="ventas",
        entorno=entorno,
        ahora=AHORA,
        ruta_directorio=ruta_directorio,
    )


def parametros(entorno):
    return entorno.herramientas[0]["script"].splitlines()


@pytest.mark.parametrize(
    "tipo, clave, objetos",
    [(TABLAS, "TABLES", ["CLIENTES", "PEDIDOS"]), (SCHEMAS, "SCHEMAS", ["HR", "VENTAS"])],
)
def test_respalda_con_la_clave_de_expdp_del_tipo(tipo, clave, objetos):
    entorno = EntornoFalso()

    resultado = respaldo(tipo, objetos, entorno)

    assert f"{clave}={','.join(objetos)}" in parametros(entorno)
    assert resultado.dmp == "ventas_20261017_153045.dmp"
    assert resultado.log == "ventas_20261017_153045.log"


@pytest.mark.parametrize("tipo", [TABLAS, SCHEMAS])
def test_si_expdp_falla_informa_error_log_y_explicacion(tipo):
    entorno = EntornoFalso(
        codigo=5, texto="salida de expdp", log="ORA-27038: el archivo creado ya existe"
    )

    with pytest.raises(RespaldoFallido) as error:
        respaldo(tipo, ["X"], entorno, ruta_directorio=RUTA)

    assert "ORA-27038" in error.value.log
    assert "Ya existe un archivo de respaldo" in error.value.explicacion
    assert "s3creta!" not in str(error.value)


def test_leer_log_devuelve_el_contenido_del_archivo_del_entorno():
    entorno = EntornoFalso(log="ORA-27038: el archivo creado ya existe")
    ruta = PurePosixPath(RUTA) / "ventas.log"

    log = leer_log(entorno, ruta)

    assert log == "ORA-27038: el archivo creado ya existe"
    assert entorno.lecturas == [ruta]


def test_el_mensaje_de_respaldo_fallido_nombra_la_herramienta():
    assert str(RespaldoFallido(5, "")) == "El respaldo falló: expdp terminó con código 5"
    assert str(RespaldoFallido(1, "", "rman")) == "El respaldo falló: rman terminó con código 1"
