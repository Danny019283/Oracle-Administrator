from pathlib import PurePosixPath

import pytest

from src.services.archivelog import FRA_DIRECTORIO, ArchivelogFallido, activar_archivelog
from src.services.entorno_oracle import OperacionEntornoFallida, Salida
from tests.services.entorno_falso import EntornoFalso

FRA = PurePosixPath("/opt/oracle/oradata/fast_recovery_area")


def sentencias(entorno):
    script = entorno.herramientas[0]["script"]
    return [linea.strip() for linea in script.splitlines() if linea.strip()]


def test_la_fra_por_defecto_es_la_de_oracle_como_ruta_posix():
    assert FRA_DIRECTORIO == FRA


def test_crea_la_carpeta_de_la_fra_y_ejecuta_sqlplus_como_sysdba_con_el_script_temporal():
    entorno = EntornoFalso()

    activar_archivelog(entorno, FRA)

    assert entorno.carpetas == [FRA]
    herramienta = entorno.herramientas[0]
    assert herramienta["nombre"] == "sqlplus"
    assert herramienta["args"][:2] == ["-S", "/ as sysdba"]
    assert herramienta["args"][2].startswith("@")
    assert herramienta["prefijo"] == "archivelog"
    assert herramienta["extension"] == ".sql"
    assert herramienta["variables"] == {"ORACLE_SID": "XE"}


def test_el_script_ya_no_crea_la_carpeta_con_host_mkdir():
    entorno = EntornoFalso()

    activar_archivelog(entorno, FRA)

    assert not any("HOST" in s.upper() or "MKDIR" in s.upper() for s in sentencias(entorno))


def test_define_la_fra_reinicia_en_mount_activa_archivelog_y_abre_la_base_en_ese_orden():
    entorno = EntornoFalso()

    activar_archivelog(entorno, FRA)

    sql = [s.upper() for s in sentencias(entorno)]
    pasos = [
        "DB_RECOVERY_FILE_DEST_SIZE",
        "DB_RECOVERY_FILE_DEST=",
        "SHUTDOWN IMMEDIATE",
        "STARTUP MOUNT",
        "ALTER DATABASE ARCHIVELOG;",
        "ALTER DATABASE OPEN;",
    ]
    posiciones = [next(i for i, s in enumerate(sql) if paso in s) for paso in pasos]
    assert posiciones == sorted(posiciones)


def test_el_destino_de_la_fra_en_el_script_es_la_ruta_recibida():
    entorno = EntornoFalso()

    activar_archivelog(entorno, PurePosixPath("/otra/fra"))

    assert "db_recovery_file_dest='/otra/fra'" in sentencias(entorno)[2]


def test_el_script_se_detiene_en_el_primer_error_de_sql():
    entorno = EntornoFalso()

    activar_archivelog(entorno, FRA)

    assert sentencias(entorno)[0] == "WHENEVER SQLERROR EXIT SQL.SQLCODE"


def test_devuelve_la_salida_de_sqlplus():
    assert activar_archivelog(EntornoFalso(texto="listo"), FRA) == "listo"


def test_si_sqlplus_falla_informa_el_error_de_oracle_con_su_log():
    entorno = EntornoFalso(salidas=[Salida(1, "ORA-19809: límite de la FRA superado")])

    with pytest.raises(ArchivelogFallido) as error:
        activar_archivelog(entorno, FRA)

    assert str(error.value) == "No se pudo activar ARCHIVELOG"
    assert "ORA-19809" in error.value.log
    assert "Se superó el límite" in error.value.explicacion


def test_si_no_se_puede_crear_la_carpeta_lanza_archivelog_fallido_y_no_ejecuta_sqlplus():
    class EntornoSinCarpeta(EntornoFalso):
        def crear_carpeta(self, ruta):
            raise OperacionEntornoFallida("mkdir: Permission denied")

    entorno = EntornoSinCarpeta()

    with pytest.raises(ArchivelogFallido) as error:
        activar_archivelog(entorno, FRA)

    assert "Permission denied" in error.value.log
    assert entorno.herramientas == []
