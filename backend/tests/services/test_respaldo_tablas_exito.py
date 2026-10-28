from datetime import datetime

from src.services.expdp_runner import Conexion
from src.services.respaldo_tablas import respaldar_tablas
from tests.services.entorno_falso import RUTA_TEMPORAL, EntornoFalso

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")


def respaldar(entorno, tablas=("CLIENTES", "PEDIDOS")):
    return respaldar_tablas(
        conexion=CONEXION,
        tablas=list(tablas),
        directorio="RESPALDO",
        nombre="ventas",
        entorno=entorno,
        ahora=AHORA,
    )


def test_devuelve_los_nombres_del_dmp_y_del_log():
    resultado = respaldar(EntornoFalso(texto="Job completado"))

    assert resultado.dmp == "ventas_20261017_153045.dmp"
    assert resultado.log == "ventas_20261017_153045.log"


def test_pide_expdp_al_entorno_con_los_parametros_en_un_parfile():
    entorno = EntornoFalso(texto="Job completado")

    respaldar(entorno)

    (herramienta,) = entorno.herramientas
    assert herramienta["nombre"] == "expdp"
    assert herramienta["args"] == [f"PARFILE={RUTA_TEMPORAL}"]
    assert herramienta["prefijo"] == "expdp"
    assert herramienta["extension"] == ".par"
    parametros = herramienta["script"].splitlines()
    assert "USERID=HR/s3creta!@XEPDB1" in parametros
    assert "TABLES=CLIENTES,PEDIDOS" in parametros
    assert "DIRECTORY=RESPALDO" in parametros
    assert "DUMPFILE=ventas_20261017_153045.dmp" in parametros
    assert "LOGFILE=ventas_20261017_153045.log" in parametros


def test_la_contrasena_nunca_viaja_en_los_argumentos_ni_en_el_resultado():
    entorno = EntornoFalso()

    resultado = respaldar(entorno)

    assert "s3creta!" not in " ".join(entorno.herramientas[0]["args"])
    assert "s3creta!" not in repr(resultado)
