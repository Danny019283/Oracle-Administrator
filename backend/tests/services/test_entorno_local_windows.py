import tempfile
from pathlib import PureWindowsPath

import pytest

from src.services.entorno_local import EntornoLocal, SistemaWindows
from src.services.entorno_oracle import ComandoHerramienta, Salida

TEMPORAL = r"C:\Users\ana\AppData\Local\Temp"


class ArchivoFalso:
    """Hace de Path de Windows: anota en `estado` lo que se le pide, sin tocar el disco."""

    def __init__(self, estado, ruta):
        self.estado = estado
        self.ruta = ruta

    def write_text(self, texto):
        self.estado["archivos"][self.ruta] = texto

    def read_text(self, errors="strict"):
        return self.estado["archivos"][self.ruta]

    def mkdir(self, parents=False, exist_ok=False):
        self.estado["carpetas"].append((self.ruta, parents, exist_ok))

    def unlink(self, missing_ok=False):
        self.estado["archivos"].pop(self.ruta, None)


class ProcesoFalso:
    def __init__(self, estado, error=None):
        self.estado = estado
        self.error = error
        self.llamadas = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append((args, entrada, variables))
        # durante la llamada el temporal ya existe con el script
        self.temporal = PureWindowsPath(args[-1].removeprefix("@"))
        self.contenido = self.estado["archivos"].get(self.temporal)
        if self.error:
            raise self.error
        return Salida(codigo=0, texto="ok")


@pytest.fixture
def estado(monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: TEMPORAL)
    return {"archivos": {}, "carpetas": []}


def entorno(estado, proceso=None):
    sistema = SistemaWindows(lambda ruta: ArchivoFalso(estado, ruta))
    return EntornoLocal(sistema, proceso or ProcesoFalso(estado))


def test_las_rutas_del_entorno_local_en_windows_son_rutas_de_windows(estado):
    assert entorno(estado).tipo_ruta is PureWindowsPath


def test_leer_archivo_lee_la_ruta_de_windows(estado):
    ruta = PureWindowsPath(r"C:\oracle\dump\expdp.log")
    estado["archivos"][ruta] = "export terminado\n"

    assert entorno(estado).leer_archivo(ruta) == "export terminado\n"


def test_crear_carpeta_crea_los_padres_de_la_ruta_de_windows(estado):
    ruta = PureWindowsPath(r"C:\oracle\dump\respaldo")

    entorno(estado).crear_carpeta(ruta)

    assert estado["carpetas"] == [(ruta, True, True)]


def test_el_temporal_va_en_el_directorio_temporal_del_perfil_con_el_script(estado):
    proceso = ProcesoFalso(estado)

    entorno(estado, proceso).ejecutar(
        ComandoHerramienta("rman", lambda ruta: ["target", "/", f"@{ruta}"], "linea1\n", prefijo="rman", extension=".rman")
    )

    assert proceso.temporal.parent == PureWindowsPath(TEMPORAL)
    assert proceso.temporal.name.startswith("rman_") and proceso.temporal.suffix == ".rman"
    assert proceso.contenido == "linea1\n"
    assert "linea1" not in " ".join(proceso.llamadas[0][0])


def test_rman_y_sqlplus_se_lanzan_local_con_oracle_sid_en_el_proceso(estado):
    proceso = ProcesoFalso(estado)
    local = entorno(estado, proceso)
    variables = {"ORACLE_SID": "ORCL"}

    local.ejecutar(ComandoHerramienta("rman", lambda r: ["target", "/", f"@{r}"], "x", prefijo="rman", variables=variables))
    local.ejecutar(
        ComandoHerramienta("sqlplus", lambda r: ["-S", "/ as sysdba", f"@{r}"], "x", prefijo="sql", variables=variables)
    )

    assert proceso.llamadas[0][0][:3] == ["rman", "target", "/"]
    assert proceso.llamadas[1][0][:3] == ["sqlplus", "-S", "/ as sysdba"]
    assert [llamada[2] for llamada in proceso.llamadas] == [variables, variables]


def test_borra_el_temporal_al_terminar_y_si_el_proceso_falla(estado):
    proceso = ProcesoFalso(estado, error=RuntimeError("falla"))
    local = entorno(estado, proceso)

    with pytest.raises(RuntimeError):
        local.ejecutar(ComandoHerramienta("rman", lambda r: [f"@{r}"], "x", prefijo="rman"))
    assert estado["archivos"] == {}

    proceso.error = None
    local.ejecutar(ComandoHerramienta("rman", lambda r: [f"@{r}"], "x", prefijo="rman"))
    assert proceso.contenido == "x"
    assert estado["archivos"] == {}
