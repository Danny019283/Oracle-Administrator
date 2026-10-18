from datetime import datetime

import pytest

from src.services.expdp_runner import Conexion, Salida
from src.services.respaldo_schemas import RespaldoFallido, respaldar_schemas

AHORA = datetime(2026, 10, 17, 15, 30, 45)
CONEXION = Conexion(usuario="SYSTEM", password="s3creta!", servicio="XEPDB1")
RUTA = "/opt/oracle/Respaldos"
LOG = "ventas_20261017_153045.log"
ERROR_DUPLICADO = (
    "ORA-39001: argumento no válido\n"
    "ORA-31641: no se puede crear el archivo de volcado\n"
    "ORA-27038: el archivo creado ya existe"
)


class EjecutorFalso:
    def __init__(self, codigo_expdp=0, log=ERROR_DUPLICADO):
        self.codigo_expdp = codigo_expdp
        self.log = log
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "expdp" in args:
            return Salida(codigo=self.codigo_expdp, texto="Job completado")
        if "cat" in args and entrada is None:
            return Salida(codigo=0, texto=self.log)
        return Salida(codigo=0, texto="")


def respaldar(ejecutor, schemas=("HR", "VENTAS"), ruta_directorio=None):
    return respaldar_schemas(
        conexion=CONEXION,
        schemas=list(schemas),
        directorio="RESPALDO",
        nombre="ventas",
        contenedor="oracle21c",
        ejecutar=ejecutor,
        ahora=AHORA,
        ruta_directorio=ruta_directorio,
    )


def llamada_expdp(ejecutor):
    return next(args for args, _ in ejecutor.llamadas if "expdp" in args)


def test_devuelve_los_nombres_del_dmp_y_del_log():
    resultado = respaldar(EjecutorFalso())

    assert resultado.dmp == "ventas_20261017_153045.dmp"
    assert resultado.log == "ventas_20261017_153045.log"


def test_ejecuta_expdp_con_schemas_en_un_parfile_dentro_del_contenedor():
    ejecutor = EjecutorFalso()

    respaldar(ejecutor)

    comando = llamada_expdp(ejecutor)
    assert comando[:3] == ["docker", "exec", "oracle21c"]
    escritura = next(entrada for _, entrada in ejecutor.llamadas if entrada is not None)
    parametros = escritura.splitlines()
    assert "USERID=SYSTEM/s3creta!@XEPDB1" in parametros
    assert "SCHEMAS=HR,VENTAS" in parametros
    assert not any(p.startswith("TABLES=") for p in parametros)
    assert "DIRECTORY=RESPALDO" in parametros
    assert "DUMPFILE=ventas_20261017_153045.dmp" in parametros
    assert "LOGFILE=ventas_20261017_153045.log" in parametros


def test_la_contrasena_nunca_viaja_en_los_argumentos_ni_en_el_resultado():
    ejecutor = EjecutorFalso()

    resultado = respaldar(ejecutor)

    for args, _ in ejecutor.llamadas:
        assert "s3creta!" not in " ".join(args)
    assert "s3creta!" not in repr(resultado)


def test_si_expdp_falla_informa_el_error_con_log_y_explicacion():
    ejecutor = EjecutorFalso(codigo_expdp=5)

    with pytest.raises(RespaldoFallido) as error:
        respaldar(ejecutor, ruta_directorio=RUTA)

    fallo = error.value
    assert fallo.log == ERROR_DUPLICADO
    assert "ORA-27038" in fallo.log
    assert "Ya existe un archivo de respaldo con ese nombre" in fallo.explicacion
    assert "s3creta!" not in str(fallo)
    lecturas = [args for args, _ in ejecutor.llamadas if "cat" in args]
    assert ["docker", "exec", "oracle21c", "cat", f"{RUTA}/{LOG}"] in lecturas


def test_al_fallar_no_borra_el_dumpfile_y_si_limpia_el_parfile():
    ejecutor = EjecutorFalso(codigo_expdp=5)

    with pytest.raises(RespaldoFallido):
        respaldar(ejecutor, ruta_directorio=RUTA)

    borrados = [args[-1] for args, _ in ejecutor.llamadas if "rm" in args]
    assert len(borrados) == 1
    assert borrados[0].endswith(".par")
