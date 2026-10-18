from src.services.expdp_runner import Conexion, Salida, ejecutar_expdp

PARAMETROS = ["SCHEMAS=HR", "DIRECTORY=RESPALDO", "DUMPFILE=ventas.dmp"]


class EjecutorFalso:
    def __init__(self):
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        return Salida(codigo=0, texto="")


def lineas_del_parfile(conexion):
    ejecutor = EjecutorFalso()
    ejecutar_expdp("oracle-test", conexion, PARAMETROS, ejecutor)
    return ejecutor, next(
        entrada for _, entrada in ejecutor.llamadas if entrada is not None
    ).splitlines()


def test_con_sesion_sysdba_el_userid_termina_en_as_sysdba_entre_comillas():
    # Sin comillas expdp rechaza el parfile: LRM-00112 (varios valores en userid).
    conexion = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", sysdba=True)

    _, lineas = lineas_del_parfile(conexion)

    assert lineas[0] == 'USERID="SYS/clave@XEPDB1 AS SYSDBA"'


def test_sin_sysdba_el_userid_no_lleva_as_sysdba():
    conexion = Conexion(usuario="HR", password="clave", servicio="XEPDB1")

    _, lineas = lineas_del_parfile(conexion)

    assert lineas[0] == "USERID=HR/clave@XEPDB1"


def test_el_resto_de_parametros_no_cambia_con_sysdba():
    conexion = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", sysdba=True)

    _, lineas = lineas_del_parfile(conexion)

    assert lineas[1:] == PARAMETROS


def test_la_password_no_aparece_en_los_argumentos_de_ningun_proceso():
    for sysdba in (False, True):
        conexion = Conexion(
            usuario="SYS", password="clave-secreta", servicio="XEPDB1", sysdba=sysdba
        )

        ejecutor, _ = lineas_del_parfile(conexion)

        for args, _entrada in ejecutor.llamadas:
            assert "clave-secreta" not in " ".join(args)


def test_el_parfile_se_borra_aunque_sea_sysdba():
    conexion = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", sysdba=True)

    ejecutor, _ = lineas_del_parfile(conexion)

    ultima = ejecutor.llamadas[-1][0]
    assert ultima[:5] == ["docker", "exec", "oracle-test", "rm", "-f"]
