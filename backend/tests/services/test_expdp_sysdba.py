from src.services.expdp_runner import Conexion, ejecutar_expdp
from tests.services.entorno_falso import RUTA_TEMPORAL, EntornoFalso

PARAMETROS = ["SCHEMAS=HR", "DIRECTORY=RESPALDO", "DUMPFILE=ventas.dmp"]


def lineas_del_parfile(conexion):
    entorno = EntornoFalso()
    ejecutar_expdp(entorno, conexion, PARAMETROS)
    return entorno, entorno.herramientas[0]["script"].splitlines()


def test_con_sesion_sysdba_el_userid_termina_en_as_sysdba_entre_comillas():
    # Sin comillas expdp rechaza el parfile: LRM-00112 (varios valores en userid).
    conexion = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", host="db.sesion", puerto=1555, sysdba=True)

    _, lineas = lineas_del_parfile(conexion)

    assert lineas[0] == 'USERID="SYS/clave@db.sesion:1555/XEPDB1 AS SYSDBA"'


def test_sin_sysdba_el_userid_no_lleva_as_sysdba():
    conexion = Conexion(usuario="HR", password="clave", servicio="XEPDB1", host="db.sesion", puerto=1555)

    _, lineas = lineas_del_parfile(conexion)

    assert lineas[0] == "USERID=HR/clave@db.sesion:1555/XEPDB1"


def test_el_resto_de_parametros_no_cambia_con_sysdba():
    conexion = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", host="db.sesion", puerto=1555, sysdba=True)

    _, lineas = lineas_del_parfile(conexion)

    assert lineas[1:] == PARAMETROS


def test_la_password_no_aparece_en_los_argumentos_de_la_herramienta():
    for sysdba in (False, True):
        conexion = Conexion(
            usuario="SYS", password="clave-secreta", servicio="XEPDB1", host="db.sesion", puerto=1555, sysdba=sysdba
        )

        entorno, _ = lineas_del_parfile(conexion)

        assert "clave-secreta" not in " ".join(entorno.herramientas[0]["args"])


def test_pide_expdp_al_entorno_con_el_parfile_como_temporal():
    conexion = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", host="db.sesion", puerto=1555, sysdba=True)

    entorno, _ = lineas_del_parfile(conexion)

    (herramienta,) = entorno.herramientas
    assert herramienta["nombre"] == "expdp"
    assert herramienta["args"] == [f"PARFILE={RUTA_TEMPORAL}"]
    assert herramienta["prefijo"] == "expdp"
    assert herramienta["extension"] == ".par"
