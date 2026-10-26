import pytest

from src.services.archivelog import ArchivelogFallido, activar_archivelog
from src.services.expdp_runner import Salida


class EjecutorFalso:
    def __init__(self, codigo_sqlplus=0, texto="Base de datos abierta"):
        self.codigo_sqlplus = codigo_sqlplus
        self.texto = texto
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "sqlplus" in args:
            return Salida(codigo=self.codigo_sqlplus, texto=self.texto)
        return Salida(codigo=0, texto="")


def sentencias(ejecutor):
    script = next(entrada for _, entrada in ejecutor.llamadas if entrada is not None)
    return [linea.strip() for linea in script.splitlines() if linea.strip()]


def test_ejecuta_sqlplus_como_sysdba_con_el_script_temporal_del_contenedor():
    ejecutor = EjecutorFalso()

    activar_archivelog("oracle-test", ejecutor)

    ruta = ejecutor.llamadas[0][0][-1].split("cat > ")[1]
    assert ejecutor.llamadas[1][0] == [
        "docker", "exec", "oracle-test",
        "env", "ORACLE_SID=XE", "sqlplus", "-S", "/ as sysdba", f"@{ruta}",
    ]
    assert ejecutor.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_define_la_fra_reinicia_en_mount_activa_archivelog_y_abre_la_base_en_ese_orden():
    ejecutor = EjecutorFalso()

    activar_archivelog("oracle-test", ejecutor)

    sql = [s.upper() for s in sentencias(ejecutor)]
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


def test_el_script_se_detiene_en_el_primer_error_de_sql():
    ejecutor = EjecutorFalso()

    activar_archivelog("oracle-test", ejecutor)

    assert sentencias(ejecutor)[0] == "WHENEVER SQLERROR EXIT SQL.SQLCODE"


def test_devuelve_la_salida_de_sqlplus():
    assert activar_archivelog("oracle-test", EjecutorFalso(texto="listo")) == "listo"


def test_si_sqlplus_falla_informa_el_error_de_oracle_con_su_log():
    ejecutor = EjecutorFalso(codigo_sqlplus=1, texto="ORA-19809: límite de la FRA superado")

    with pytest.raises(ArchivelogFallido) as error:
        activar_archivelog("oracle-test", ejecutor)

    assert str(error.value) == "No se pudo activar ARCHIVELOG"
    assert "ORA-19809" in error.value.log
    assert "Se superó el límite" in error.value.explicacion
