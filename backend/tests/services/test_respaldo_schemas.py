from datetime import datetime
from pathlib import PurePosixPath

import pytest

from src.services.expdp_runner import Conexion
from src.services.respaldo_schemas import RespaldoFallido, respaldar_schemas
from tests.services.entorno_falso import RUTA_TEMPORAL, EntornoFalso

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="SYSTEM", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"
LOG = "ventas_20261017_153045.log"
ERROR_DUPLICADO = (
    "ORA-39001: argumento no válido\n"
    "ORA-31641: no se puede crear el archivo de volcado\n"
    "ORA-27038: el archivo creado ya existe"
)


def respaldar(entorno, schemas=("HR", "VENTAS"), ruta_directorio=None):
    return respaldar_schemas(
        conexion=CONEXION,
        schemas=list(schemas),
        directorio="RESPALDO",
        nombre="ventas",
        entorno=entorno,
        ahora=AHORA,
        ruta_directorio=ruta_directorio,
    )


def test_devuelve_los_nombres_del_dmp_y_del_log():
    resultado = respaldar(EntornoFalso(texto="Job completado"))

    assert resultado.dmp == "ventas_20261017_153045.dmp"
    assert resultado.log == "ventas_20261017_153045.log"


def test_pide_expdp_al_entorno_con_schemas_en_un_parfile():
    entorno = EntornoFalso(texto="Job completado")

    respaldar(entorno)

    (herramienta,) = entorno.herramientas
    assert herramienta["nombre"] == "expdp"
    assert herramienta["args"] == [f"PARFILE={RUTA_TEMPORAL}"]
    parametros = herramienta["script"].splitlines()
    assert "USERID=SYSTEM/s3creta!@XEPDB1" in parametros
    assert "SCHEMAS=HR,VENTAS" in parametros
    assert not any(p.startswith("TABLES=") for p in parametros)
    assert "DIRECTORY=RESPALDO" in parametros
    assert "DUMPFILE=ventas_20261017_153045.dmp" in parametros
    assert "LOGFILE=ventas_20261017_153045.log" in parametros


def test_la_contrasena_nunca_viaja_en_los_argumentos_ni_en_el_resultado():
    entorno = EntornoFalso()

    resultado = respaldar(entorno)

    assert "s3creta!" not in " ".join(entorno.herramientas[0]["args"])
    assert "s3creta!" not in repr(resultado)


def test_si_expdp_falla_informa_el_error_con_log_y_explicacion():
    entorno = EntornoFalso(codigo=5, texto="Job completado", log=ERROR_DUPLICADO)

    with pytest.raises(RespaldoFallido) as error:
        respaldar(entorno, ruta_directorio=RUTA)

    fallo = error.value
    assert fallo.log == ERROR_DUPLICADO
    assert "ORA-27038" in fallo.log
    assert "Ya existe un archivo de respaldo con ese nombre" in fallo.explicacion
    assert "s3creta!" not in str(fallo)
    assert entorno.lecturas == [PurePosixPath(RUTA) / LOG]
