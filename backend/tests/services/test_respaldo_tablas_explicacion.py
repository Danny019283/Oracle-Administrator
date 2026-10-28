from datetime import datetime

import pytest

from src.services.errores_oracle import EXPLICACION_GENERICA
from src.services.expdp_runner import Conexion
from src.services.respaldo_tablas import RespaldoFallido, respaldar_tablas
from tests.services.entorno_falso import EntornoFalso

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"


def fallo_de(log, salida_expdp="salida de expdp", ruta_directorio=RUTA):
    with pytest.raises(RespaldoFallido) as error:
        respaldar_tablas(
            conexion=CONEXION,
            tablas=["CLIENTES"],
            directorio="RESPALDO",
            nombre="ventas",
            entorno=EntornoFalso(codigo=5, texto=salida_expdp, log=log),
            ahora=AHORA,
            ruta_directorio=ruta_directorio,
        )
    return error.value


def test_el_fallo_incluye_el_error_de_oracle_la_explicacion_y_el_log():
    log = "ORA-31641: no se puede crear el archivo\nORA-27038: el archivo creado ya existe"

    fallo = fallo_de(log)

    assert fallo.log == log
    assert "ORA-27038" in fallo.log
    assert fallo.explicacion == "Ya existe un archivo de respaldo con ese nombre en el directorio"


def test_un_error_ora_desconocido_da_la_explicacion_generica_y_conserva_el_log():
    fallo = fallo_de("ORA-99999: error raro")

    assert fallo.explicacion == EXPLICACION_GENERICA
    assert fallo.log == "ORA-99999: error raro"


def test_sin_ruta_del_directorio_explica_a_partir_de_la_salida_de_expdp():
    fallo = fallo_de(
        log="",
        salida_expdp="ORA-01017: usuario/contraseña no válidos",
        ruta_directorio=None,
    )

    assert fallo.explicacion == "Usuario o contraseña de Oracle incorrectos"
