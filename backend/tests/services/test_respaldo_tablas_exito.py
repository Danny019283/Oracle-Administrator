from datetime import datetime

from src.services.expdp_runner import Conexion, Salida
from src.services.respaldo_tablas import respaldar_tablas

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")


class EjecutorFalso:
    def __init__(self, codigo_expdp=0):
        self.codigo_expdp = codigo_expdp
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "expdp" in args:
            return Salida(codigo=self.codigo_expdp, texto="Job completado")
        return Salida(codigo=0, texto="")


def respaldar(ejecutor, tablas=("CLIENTES", "PEDIDOS")):
    return respaldar_tablas(
        conexion=CONEXION,
        tablas=list(tablas),
        directorio="RESPALDO",
        nombre="ventas",
        contenedor="oracle21c",
        ejecutar=ejecutor,
        ahora=AHORA,
    )


def llamada_expdp(ejecutor):
    return next(args for args, _ in ejecutor.llamadas if "expdp" in args)


def test_devuelve_los_nombres_del_dmp_y_del_log():
    resultado = respaldar(EjecutorFalso())

    assert resultado.dmp == "ventas_20261017_153045.dmp"
    assert resultado.log == "ventas_20261017_153045.log"


def test_ejecuta_expdp_dentro_del_contenedor_con_los_parametros_en_un_parfile():
    ejecutor = EjecutorFalso()

    respaldar(ejecutor)

    comando = llamada_expdp(ejecutor)
    assert comando[:3] == ["docker", "exec", "oracle21c"]
    parfile_arg = next(a for a in comando if a.startswith("PARFILE="))

    escritura = next(
        (args, entrada) for args, entrada in ejecutor.llamadas if entrada is not None
    )
    assert parfile_arg.removeprefix("PARFILE=") in " ".join(escritura[0])
    parametros = escritura[1].splitlines()
    assert "USERID=HR/s3creta!@XEPDB1" in parametros
    assert "TABLES=CLIENTES,PEDIDOS" in parametros
    assert "DIRECTORY=RESPALDO" in parametros
    assert "DUMPFILE=ventas_20261017_153045.dmp" in parametros
    assert "LOGFILE=ventas_20261017_153045.log" in parametros


def test_la_contrasena_nunca_viaja_en_los_argumentos_ni_en_el_resultado():
    ejecutor = EjecutorFalso()

    resultado = respaldar(ejecutor)

    for args, _ in ejecutor.llamadas:
        assert "s3creta!" not in " ".join(args)
    assert "s3creta!" not in repr(resultado)


def test_borra_el_parfile_al_terminar():
    ejecutor = EjecutorFalso()

    respaldar(ejecutor)

    parfile = llamada_expdp(ejecutor)[-1].removeprefix("PARFILE=")
    ultimo, _ = ejecutor.llamadas[-1]
    assert ultimo[:3] == ["docker", "exec", "oracle21c"]
    assert ultimo[3:5] == ["rm", "-f"]
    assert ultimo[-1] == parfile
