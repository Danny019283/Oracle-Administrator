import pytest

from src.services.entorno_oracle import HerramientaNoDisponible, Salida
from src.services.expdp_runner import Conexion, ejecutar_impdp
from tests.services.entorno_falso import RUTA_TEMPORAL, EntornoFalso

PARAMETROS = ["DIRECTORY=RESPALDO", "DUMPFILE=ventas_20260101_101010.dmp", "TABLES=HR.EMPLEADOS"]


def ejecutar(sysdba, password="clave-secreta", entorno=None):
    entorno = entorno or EntornoFalso()
    conexion = Conexion(usuario="SYS", password=password, servicio="XEPDB1", host="db.sesion", puerto=1555, sysdba=sysdba)
    ejecutar_impdp(entorno, conexion, PARAMETROS)
    return entorno.herramientas[0]


def test_ejecuta_impdp_con_solo_el_parfile_como_argumento():
    herramienta = ejecutar(sysdba=False)

    assert herramienta["nombre"] == "impdp"
    assert herramienta["args"] == [f"PARFILE={RUTA_TEMPORAL}"]
    assert herramienta["prefijo"] == "impdp"
    assert herramienta["extension"] == ".par"


def test_la_password_solo_va_en_el_parfile():
    herramienta = ejecutar(sysdba=False)

    assert "clave-secreta" not in " ".join(herramienta["args"])
    assert herramienta["script"].splitlines() == ["USERID=SYS/clave-secreta@db.sesion:1555/XEPDB1", *PARAMETROS]


def test_con_sesion_sysdba_el_userid_lleva_as_sysdba_entre_comillas():
    herramienta = ejecutar(sysdba=True)

    assert herramienta["script"].splitlines()[0] == 'USERID="SYS/clave-secreta@db.sesion:1555/XEPDB1 AS SYSDBA"'


def test_devuelve_la_salida_de_impdp():
    entorno = EntornoFalso(codigo=5, texto="ORA-39151")
    conexion = Conexion(usuario="SYS", password="x", servicio="XEPDB1", sysdba=True)

    assert ejecutar_impdp(entorno, conexion, PARAMETROS) == Salida(codigo=5, texto="ORA-39151")


def test_si_impdp_no_esta_deja_pasar_herramienta_no_disponible():
    class SinImpdp(EntornoFalso):
        def ejecutar(self, comando):
            raise HerramientaNoDisponible(comando.nombre)

    with pytest.raises(HerramientaNoDisponible, match="impdp"):
        ejecutar_impdp(SinImpdp(), Conexion(usuario="SYS", password="x", servicio="XEPDB1"), PARAMETROS)
