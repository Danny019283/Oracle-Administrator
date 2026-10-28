import pytest

from src.services.directorios import Directorio
from src.services.entorno_oracle import Salida
from src.services.respaldo import RespaldoFallido, SolicitudInvalida
from src.services.respaldo_full import SinArchivelog, en_archivelog, respaldar_full
from tests.services.entorno_falso import EntornoFalso

RUTA = "/opt/oracle/Respaldos"
DIRECTORIOS = [Directorio("RESPALDO", RUTA), Directorio("OTRO", "/tmp/otro")]


class ConsultaFalsa:
    def __init__(self, modo="ARCHIVELOG"):
        self.modo = modo
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)
        return [(self.modo,)]


def entorno_con(codigos=(0, 0), textos=("log del backup", "log de la limpieza")):
    """Entorno falso con la salida de cada ejecución de RMAN, en orden (backup, limpieza)."""
    return EntornoFalso(salidas=[Salida(c, t) for c, t in zip(codigos, textos)])


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
    assert f"FORMAT '{RUTA}/semanal_%d_%T_%s_%p'" in script
    assert "DELETE" not in script


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


def test_el_exito_devuelve_el_log_del_backup_sin_advertencia():
    resultado = respaldo()

    assert resultado.log == "log del backup"
    assert resultado.advertencia is None


def test_si_el_backup_falla_informa_el_error_con_su_log_y_no_ejecuta_la_limpieza():
    entorno = entorno_con(
        codigos=(1,), textos=("RMAN-03002: fallo\nRMAN-06059: falta un archivelog",)
    )

    with pytest.raises(RespaldoFallido) as error:
        respaldo(entorno)

    assert "rman terminó con código 1" in str(error.value)
    assert "RMAN-06059" in error.value.log
    assert "Faltan archivelogs" in error.value.explicacion
    assert len(scripts(entorno)) == 1


def test_si_la_limpieza_falla_el_respaldo_es_exitoso_con_advertencia():
    entorno = entorno_con(codigos=(0, 1), textos=("log del backup", "RMAN-06059: falta"))

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
