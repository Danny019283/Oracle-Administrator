from datetime import datetime

import pytest

from src.services.expdp_runner import Conexion, Salida
from src.services.respaldo import (
    SCHEMAS,
    TABLAS,
    RespaldoFallido,
    respaldar,
)

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"


class EjecutorFalso:
    def __init__(self, codigo_expdp=0):
        self.codigo_expdp = codigo_expdp
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "expdp" in args:
            return Salida(codigo=self.codigo_expdp, texto="salida de expdp")
        if "cat" in args and entrada is None:
            return Salida(codigo=0, texto="ORA-27038: el archivo creado ya existe")
        return Salida(codigo=0, texto="")


def respaldo(tipo, objetos, ejecutor, ruta_directorio=None):
    return respaldar(
        tipo=tipo,
        conexion=CONEXION,
        objetos=objetos,
        directorio="RESPALDO",
        nombre="ventas",
        contenedor="oracle21c",
        ejecutar=ejecutor,
        ahora=AHORA,
        ruta_directorio=ruta_directorio,
    )


def parametros(ejecutor):
    entrada = next(entrada for _, entrada in ejecutor.llamadas if entrada is not None)
    return entrada.splitlines()


@pytest.mark.parametrize(
    "tipo, clave, objetos",
    [(TABLAS, "TABLES", ["CLIENTES", "PEDIDOS"]), (SCHEMAS, "SCHEMAS", ["HR", "VENTAS"])],
)
def test_respalda_con_la_clave_de_expdp_del_tipo(tipo, clave, objetos):
    ejecutor = EjecutorFalso()

    resultado = respaldo(tipo, objetos, ejecutor)

    assert f"{clave}={','.join(objetos)}" in parametros(ejecutor)
    assert resultado.dmp == "ventas_20261017_153045.dmp"
    assert resultado.log == "ventas_20261017_153045.log"


@pytest.mark.parametrize("tipo", [TABLAS, SCHEMAS])
def test_si_expdp_falla_informa_error_log_y_explicacion(tipo):
    ejecutor = EjecutorFalso(codigo_expdp=5)

    with pytest.raises(RespaldoFallido) as error:
        respaldo(tipo, ["X"], ejecutor, ruta_directorio=RUTA)

    assert "ORA-27038" in error.value.log
    assert "Ya existe un archivo de respaldo" in error.value.explicacion
    assert "s3creta!" not in str(error.value)
