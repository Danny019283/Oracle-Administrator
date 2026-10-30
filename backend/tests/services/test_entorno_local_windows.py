import tempfile
from pathlib import PureWindowsPath

import pytest

from src.services.entorno_local import EntornoLocal, SistemaWindows
from src.services.entorno_oracle import ArchivoEntorno, ComandoHerramienta, OperacionEntornoFallida, Salida

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
        if self.estado.get("fallo_borrado"):
            raise PermissionError("Acceso denegado")
        self.estado["archivos"].pop(self.ruta, None)

    def iterdir(self):
        if self.ruta not in self.estado.get("listados", {}):
            raise FileNotFoundError(str(self.ruta))
        return iter(self.estado["listados"][self.ruta])


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


class EjecutorSecuencia:
    """Ejecutor falso: devuelve las salidas dadas en orden y anota los argumentos de cada llamada."""

    def __init__(self, *salidas):
        self.salidas = list(salidas)
        self.llamadas = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append(args)
        return self.salidas.pop(0)


CLAVE = "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\OracleServiceORCL"
CONSULTA_REG = ["reg", "query", r"HKLM\SYSTEM\CurrentControlSet\Services\OracleServiceORCL", "/v", "ObjectName"]


def salida_reg(cuenta):
    return Salida(codigo=0, texto=f"\n{CLAVE}\n    ObjectName    REG_SZ    {cuenta}\n\n")


RUTA = PureWindowsPath(r"C:\respaldos")


@pytest.mark.parametrize(
    "cuenta_reg, cuenta_icacls",
    [
        ("oracleuser", "oracleuser"),
        ("LocalSystem", "SYSTEM"),
        (r"DOMINIO\svc_oracle", r"DOMINIO\svc_oracle"),
    ],
)
def test_dar_permisos_otorga_modificar_a_la_cuenta_del_servicio(cuenta_reg, cuenta_icacls):
    ejecutor = EjecutorSecuencia(salida_reg(cuenta_reg), Salida(codigo=0, texto="ok"))

    SistemaWindows().dar_permisos_a_oracle(RUTA, "ORCL", ejecutor)

    assert ejecutor.llamadas == [
        CONSULTA_REG,
        ["icacls", str(RUTA), "/grant", f"{cuenta_icacls}:(OI)(CI)M"],
    ]


def test_dar_permisos_con_la_salida_real_de_reg_conserva_el_espacio_interno_de_la_cuenta():
    texto = (
        "\r\nHKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\OracleServiceXE\r\n"
        "    ObjectName    REG_SZ    NT SERVICE\\OracleServiceXE\r\n\r\n"
    )
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto=texto), Salida(codigo=0, texto="ok"))

    SistemaWindows().dar_permisos_a_oracle(RUTA, "XE", ejecutor)

    assert ejecutor.llamadas[1] == ["icacls", str(RUTA), "/grant", r"NT SERVICE\OracleServiceXE:(OI)(CI)M"]


def test_dar_permisos_con_reg_fallido_no_ejecuta_icacls():
    ejecutor = EjecutorSecuencia(Salida(codigo=1, texto="ERROR: El sistema no puede encontrar la clave"))

    with pytest.raises(OperacionEntornoFallida, match="reg query.*El sistema no puede encontrar la clave"):
        SistemaWindows().dar_permisos_a_oracle(RUTA, "ORCL", ejecutor)

    assert len(ejecutor.llamadas) == 1


def test_dar_permisos_sin_objectname_en_la_salida_de_reg_falla_con_mensaje_claro():
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto=f"\n{CLAVE}\n"))

    with pytest.raises(OperacionEntornoFallida, match="reg query"):
        SistemaWindows().dar_permisos_a_oracle(RUTA, "ORCL", ejecutor)

    assert len(ejecutor.llamadas) == 1


def test_dar_permisos_ignora_cabeceras_y_mensajes_en_espanol_de_reg():
    texto = (
        "Fin de la búsqueda: 1 coincidencias encontradas.\n"
        f"{CLAVE}\n"
        "    ObjectName    REG_SZ    LocalSystem\n"
        "ERROR: Acceso denegado a otra clave REG_SZ\n"
    )
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto=texto), Salida(codigo=0, texto="ok"))

    SistemaWindows().dar_permisos_a_oracle(RUTA, "ORCL", ejecutor)

    assert ejecutor.llamadas[1] == ["icacls", str(RUTA), "/grant", "SYSTEM:(OI)(CI)M"]


def test_dar_permisos_con_icacls_fallido_lanza_error_con_su_salida():
    ejecutor = EjecutorSecuencia(salida_reg("LocalSystem"), Salida(codigo=5, texto="Acceso denegado"))

    with pytest.raises(OperacionEntornoFallida, match="icacls.*Acceso denegado"):
        SistemaWindows().dar_permisos_a_oracle(RUTA, "ORCL", ejecutor)


class EntradaFalsa:
    def __init__(self, nombre, tamano, modificado, archivo=True):
        self.name = nombre
        self.archivo = archivo
        self._stat = type("Stat", (), {"st_size": tamano, "st_mtime": modificado})()

    def is_file(self):
        return self.archivo

    def stat(self):
        return self._stat


def test_listar_archivos_lista_solo_los_archivos_de_la_ruta_de_windows(estado):
    ruta = PureWindowsPath(r"C:\oracle\dump")
    estado["listados"] = {
        ruta: [EntradaFalsa("a_20240101_101010.dmp", 7, 1704103810.0), EntradaFalsa("sub", 0, 1.0, archivo=False)]
    }

    assert entorno(estado).listar_archivos(ruta) == [ArchivoEntorno("a_20240101_101010.dmp", 7, 1704103810.0)]


def test_listar_archivos_de_una_carpeta_ilegible_en_windows_lanza_operacion_entorno_fallida(estado):
    with pytest.raises(OperacionEntornoFallida):
        entorno(estado).listar_archivos(PureWindowsPath(r"C:\no\existe"))


def test_borrar_archivo_borra_la_ruta_de_windows(estado):
    ruta = PureWindowsPath(r"C:\oracle\dump\a.dmp")
    estado["archivos"][ruta] = "x"

    entorno(estado).borrar_archivo(ruta)

    assert ruta not in estado["archivos"]


def test_borrar_archivo_con_error_de_es_en_windows_lanza_operacion_entorno_fallida(estado):
    estado["fallo_borrado"] = True

    with pytest.raises(OperacionEntornoFallida, match="Acceso denegado"):
        entorno(estado).borrar_archivo(PureWindowsPath(r"C:\oracle\dump\a.dmp"))


def test_borrar_carpeta_borra_la_carpeta_de_windows_con_su_contenido(tmp_path):
    carpeta = tmp_path / "aux_a"
    carpeta.mkdir()
    (carpeta / "a.dbf").write_text("x")

    EntornoLocal(SistemaWindows(lambda ruta: carpeta)).borrar_carpeta(PureWindowsPath(r"C:\oracle\dump\aux_a"))

    assert not carpeta.exists()


def test_borrar_carpeta_con_error_de_es_en_windows_lanza_operacion_entorno_fallida(tmp_path):
    with pytest.raises(OperacionEntornoFallida):
        EntornoLocal(SistemaWindows(lambda ruta: tmp_path / "no_existe")).borrar_carpeta(
            PureWindowsPath(r"C:\oracle\dump\aux_a")
        )
