import pytest

from src.services.directorios import Directorio
from src.services.expdp_runner import Salida
from src.services.respaldo import RespaldoFallido, SolicitudInvalida
from src.services.respaldo_full import SinArchivelog, en_archivelog, respaldar_full

RUTA = "/opt/oracle/Respaldos"
DIRECTORIOS = [Directorio("RESPALDO", RUTA), Directorio("OTRO", "/tmp/otro")]


class ConsultaFalsa:
    def __init__(self, modo="ARCHIVELOG"):
        self.modo = modo
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)
        return [(self.modo,)]


class EjecutorFalso:
    """Registra los scripts de RMAN; `codigos` da el código de salida de cada
    ejecución de RMAN, en orden (backup, limpieza)."""

    def __init__(self, codigos=(0, 0), textos=("log del backup", "log de la limpieza")):
        self.codigos = list(codigos)
        self.textos = list(textos)
        self.llamadas = []
        self.scripts = []
        self._script = None

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if entrada is not None:
            self._script = entrada
        if "rman" in args:
            self.scripts.append(self._script)
            indice = len(self.scripts) - 1
            return Salida(codigo=self.codigos[indice], texto=self.textos[indice])
        return Salida(codigo=0, texto="")


def respaldo(ejecutor=None, consulta=None, directorio="RESPALDO", nombre="semanal"):
    ejecutor = ejecutor or EjecutorFalso()
    return respaldar_full(
        consulta=consulta or ConsultaFalsa(),
        directorios=DIRECTORIOS,
        directorio=directorio,
        nombre=nombre,
        contenedor="oracle21c",
        ejecutar=ejecutor,
    )


@pytest.mark.parametrize("modo, esperado", [("ARCHIVELOG", True), ("NOARCHIVELOG", False)])
def test_en_archivelog_consulta_el_modo_de_log_de_la_base(modo, esperado):
    consulta = ConsultaFalsa(modo)

    assert en_archivelog(consulta) is esperado
    assert "v$database" in consulta.sqls[0].lower()


def test_el_backup_es_incremental_nivel_0_de_toda_la_base_en_la_ruta_del_directorio():
    ejecutor = EjecutorFalso()

    respaldo(ejecutor)

    script = ejecutor.scripts[0]
    assert "BACKUP INCREMENTAL LEVEL 0" in script
    assert "DATABASE" in script
    assert f"FORMAT '{RUTA}/semanal_%d_%T_%s_%p'" in script
    assert "DELETE" not in script


def test_tras_un_backup_correcto_ejecuta_la_limpieza_con_redundancy_1():
    ejecutor = EjecutorFalso()

    respaldo(ejecutor)

    assert len(ejecutor.scripts) == 2
    limpieza = ejecutor.scripts[1]
    assert "CROSSCHECK BACKUP;" in limpieza
    assert "CROSSCHECK ARCHIVELOG ALL;" in limpieza
    assert "DELETE NOPROMPT OBSOLETE REDUNDANCY 1;" in limpieza
    assert "BACKUP INCREMENTAL" not in limpieza


def test_el_exito_devuelve_el_log_del_backup_sin_advertencia():
    resultado = respaldo(EjecutorFalso())

    assert resultado.log == "log del backup"
    assert resultado.advertencia is None


def test_si_el_backup_falla_informa_el_error_con_su_log_y_no_ejecuta_la_limpieza():
    ejecutor = EjecutorFalso(
        codigos=(1,), textos=("RMAN-03002: fallo\nRMAN-06059: falta un archivelog",)
    )

    with pytest.raises(RespaldoFallido) as error:
        respaldo(ejecutor)

    assert "rman terminó con código 1" in str(error.value)
    assert "RMAN-06059" in error.value.log
    assert "Faltan archivelogs" in error.value.explicacion
    assert len(ejecutor.scripts) == 1


def test_si_la_limpieza_falla_el_respaldo_es_exitoso_con_advertencia():
    ejecutor = EjecutorFalso(codigos=(0, 1), textos=("log del backup", "RMAN-06059: falta"))

    resultado = respaldo(ejecutor)

    assert resultado.log == "log del backup"
    assert "Faltan archivelogs" in resultado.advertencia.explicacion
    assert resultado.advertencia.log == "RMAN-06059: falta"


def test_sin_archivelog_no_ejecuta_rman():
    ejecutor = EjecutorFalso()

    with pytest.raises(SinArchivelog) as error:
        respaldo(ejecutor, consulta=ConsultaFalsa("NOARCHIVELOG"))

    assert "ARCHIVELOG" in str(error.value)
    assert ejecutor.llamadas == []


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
    ejecutor = EjecutorFalso()
    consulta = ConsultaFalsa()

    with pytest.raises(SolicitudInvalida) as error:
        respaldo(ejecutor, consulta, directorio, nombre)

    assert error.value.errores == errores
    assert ejecutor.llamadas == []
    assert consulta.sqls == []
