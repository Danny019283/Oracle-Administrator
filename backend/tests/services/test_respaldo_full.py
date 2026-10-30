from datetime import datetime
from pathlib import PurePosixPath

import pytest

from src.services.directorios import Directorio
from src.services.entorno_oracle import Salida
from src.services.respaldo import RespaldoFallido, SolicitudInvalida
from src.services.respaldo_full import SinArchivelog, en_archivelog, respaldar_full
from tests.services.entorno_falso import EntornoFalso

RUTA = "/opt/oracle/Respaldos"
DIRECTORIOS = [Directorio("RESPALDO", RUTA), Directorio("OTRO", "/tmp/otro")]
AHORA = datetime(2026, 3, 5, 14, 7, 9)
BASE = "semanal_20260305_140709"


class ConsultaFalsa:
    def __init__(self, modo="ARCHIVELOG"):
        self.modo = modo
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)
        return [(self.modo,)]


def entorno_con(
    codigos=(0, 0), textos=("RMAN> 2> 3>", "log de la limpieza"), log="log del backup"
):
    """Entorno falso con la salida de cada ejecución de RMAN, en orden (backup, limpieza).

    Con `log=` RMAN solo deja el eco de prompts en la salida: el log real está en el archivo.
    """
    return EntornoFalso(salidas=[Salida(c, t) for c, t in zip(codigos, textos)], log=log)


def scripts(entorno):
    return [h["script"] for h in entorno.herramientas]


def respaldo(entorno=None, consulta=None, directorio="RESPALDO", nombre="semanal", sid="XE"):
    return respaldar_full(
        consulta=consulta or ConsultaFalsa(),
        directorios=DIRECTORIOS,
        directorio=directorio,
        nombre=nombre,
        entorno=entorno or entorno_con(),
        sid=sid,
        ahora=AHORA,
    )


@pytest.mark.parametrize("modo, esperado", [("ARCHIVELOG", True), ("NOARCHIVELOG", False)])
def test_en_archivelog_consulta_el_modo_de_log_de_la_base(modo, esperado):
    consulta = ConsultaFalsa(modo)

    assert en_archivelog(consulta) is esperado
    assert "v$database" in consulta.sqls[0].lower()


def test_el_backup_es_incremental_nivel_0_de_toda_la_base_en_la_ruta_del_directorio():
    entorno = entorno_con()

    respaldo(entorno)

    script = scripts(entorno)[0]
    assert "BACKUP INCREMENTAL LEVEL 0" in script
    assert "DATABASE" in script
    assert f"FORMAT '{RUTA}/{BASE}_%d_%s_%p.dbf'" in script
    assert "DELETE" not in script


def test_rman_escribe_el_log_junto_a_las_piezas_con_el_argumento_log_y_sin_spool():
    entorno = entorno_con()

    respaldo(entorno)

    assert f"log={RUTA}/{BASE}.log" in entorno.herramientas[0]["args"]
    assert not any(a.startswith("log=") for a in entorno.herramientas[1]["args"])
    assert all("SPOOL" not in s for s in scripts(entorno))


def test_tras_un_backup_correcto_ejecuta_la_limpieza_con_redundancy_1():
    entorno = entorno_con()

    respaldo(entorno)

    assert len(scripts(entorno)) == 2
    limpieza = scripts(entorno)[1]
    assert "CROSSCHECK BACKUP;" in limpieza
    assert "CROSSCHECK ARCHIVELOG ALL;" in limpieza
    assert "DELETE NOPROMPT OBSOLETE REDUNDANCY 1;" in limpieza
    assert "BACKUP INCREMENTAL" not in limpieza


def test_las_dos_ejecuciones_de_rman_usan_el_sid_recibido_en_oracle_sid():
    entorno = entorno_con()

    respaldo(entorno, sid="ORCL")

    assert [h["variables"] for h in entorno.herramientas] == [{"ORACLE_SID": "ORCL"}] * 2


def test_el_exito_devuelve_el_log_leido_del_archivo_sin_advertencia():
    entorno = entorno_con()

    resultado = respaldo(entorno)

    assert resultado.log == "log del backup"
    assert resultado.advertencia is None
    assert entorno.lecturas == [PurePosixPath(f"{RUTA}/{BASE}.log")]


def test_si_el_backup_falla_informa_el_error_con_el_log_del_archivo_y_no_ejecuta_la_limpieza():
    entorno = entorno_con(
        codigos=(1,), textos=("RMAN> 2>",), log="RMAN-03002: fallo\nRMAN-06059: falta un archivelog"
    )

    with pytest.raises(RespaldoFallido) as error:
        respaldo(entorno)

    assert "rman terminó con código 1" in str(error.value)
    assert "RMAN-06059" in error.value.log
    assert "Faltan archivelogs" in error.value.explicacion
    assert len(scripts(entorno)) == 1


def test_si_no_se_puede_leer_el_log_usa_la_salida_de_rman():
    exito = respaldo(entorno_con(textos=("salida de rman", "limpieza"), log=None))
    entorno = entorno_con(codigos=(1,), textos=("RMAN-06059: falta",), log=None)

    with pytest.raises(RespaldoFallido) as error:
        respaldo(entorno)

    assert exito.log == "salida de rman"
    assert error.value.log == "RMAN-06059: falta"


def test_si_la_limpieza_falla_el_respaldo_es_exitoso_con_advertencia():
    entorno = entorno_con(codigos=(0, 1), textos=("RMAN> 2>", "RMAN-06059: falta"))

    resultado = respaldo(entorno)

    assert resultado.log == "log del backup"
    assert "Faltan archivelogs" in resultado.advertencia.explicacion
    assert resultado.advertencia.log == "RMAN-06059: falta"


def test_sin_archivelog_no_ejecuta_rman():
    entorno = entorno_con()

    with pytest.raises(SinArchivelog) as error:
        respaldo(entorno, consulta=ConsultaFalsa("NOARCHIVELOG"))

    assert "ARCHIVELOG" in str(error.value)
    assert entorno.herramientas == []


@pytest.mark.parametrize(
    "directorio, nombre, errores",
    [
        ("", "semanal", ["Debes elegir un directorio"]),
        ("INEXISTENTE", "semanal", ["El directorio INEXISTENTE no está disponible"]),
        ("RESPALDO", "", ["Debes ingresar un nombre de dumpfile"]),
        (
            "RESPALDO",
            "con espacios",
            ["El nombre admite letras, números, '_' y '-', de 1 a 50 caracteres"],
        ),
        (
            "",
            "",
            ["Debes elegir un directorio", "Debes ingresar un nombre de dumpfile"],
        ),
    ],
)
def test_solicitud_invalida_informa_cada_dato_y_no_ejecuta_rman(directorio, nombre, errores):
    entorno = entorno_con()
    consulta = ConsultaFalsa()

    with pytest.raises(SolicitudInvalida) as error:
        respaldo(entorno, consulta, directorio, nombre)

    assert error.value.errores == errores
    assert entorno.herramientas == []
    assert consulta.sqls == []
