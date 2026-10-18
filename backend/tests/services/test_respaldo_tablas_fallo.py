from datetime import datetime

import pytest

from src.services.expdp_runner import Conexion, Salida
from src.services.respaldo_tablas import RespaldoFallido, respaldar_tablas

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"
LOG = "ventas_20261017_153045.log"
ERROR_DUPLICADO = (
    "ORA-39001: argumento no válido\n"
    "ORA-31641: no se puede crear el archivo de volcado\n"
    "ORA-27038: el archivo creado ya existe"
)


class EjecutorFalso:
    def __init__(self, texto_expdp="ORA-39002: operación no válida", log=ERROR_DUPLICADO):
        self.texto_expdp = texto_expdp
        self.log = log
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "expdp" in args:
            return Salida(codigo=5, texto=self.texto_expdp)
        if "cat" in args and entrada is None:
            return Salida(codigo=0, texto=self.log)
        return Salida(codigo=0, texto="")


def respaldar(ejecutor):
    return respaldar_tablas(
        conexion=CONEXION,
        tablas=["CLIENTES"],
        directorio="RESPALDO",
        nombre="ventas",
        contenedor="oracle21c",
        ejecutar=ejecutor,
        ahora=AHORA,
        ruta_directorio=RUTA,
    )


def fallo_de(ejecutor):
    with pytest.raises(RespaldoFallido) as error:
        respaldar(ejecutor)
    return error.value


def test_si_expdp_falla_informa_el_error_con_el_contenido_del_log():
    fallo = fallo_de(EjecutorFalso())

    assert fallo.log == ERROR_DUPLICADO
    assert "ORA-27038" in fallo.log


def test_lee_el_log_del_directorio_dentro_del_contenedor():
    ejecutor = EjecutorFalso()

    fallo_de(ejecutor)

    lecturas = [args for args, _ in ejecutor.llamadas if "cat" in args]
    assert ["docker", "exec", "oracle21c", "cat", f"{RUTA}/{LOG}"] in lecturas


def test_el_mensaje_del_fallo_no_incluye_la_contrasena():
    fallo = fallo_de(EjecutorFalso())

    assert "s3creta!" not in str(fallo)
    assert "s3creta!" not in fallo.log


def test_no_borra_ni_sobrescribe_el_dumpfile_y_si_limpia_el_parfile():
    ejecutor = EjecutorFalso()

    fallo_de(ejecutor)

    borrados = [args[-1] for args, _ in ejecutor.llamadas if "rm" in args]
    assert len(borrados) == 1
    assert borrados[0].endswith(".par")
    for args, _ in ejecutor.llamadas:
        assert not any(a.endswith(".dmp") for a in args if a.startswith("/"))


def test_si_no_hay_ruta_del_directorio_informa_la_salida_de_expdp():
    ejecutor = EjecutorFalso(texto_expdp="ORA-39002: operación no válida")

    with pytest.raises(RespaldoFallido) as error:
        respaldar_tablas(
            conexion=CONEXION,
            tablas=["CLIENTES"],
            directorio="RESPALDO",
            nombre="ventas",
            contenedor="oracle21c",
            ejecutar=ejecutor,
            ahora=AHORA,
        )

    assert error.value.log == "ORA-39002: operación no válida"
