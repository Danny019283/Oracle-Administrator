import dataclasses
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services import respaldos_programados as rp
from src.services.entorno_oracle import ArchivoEntorno, ArchivoNoLegible, Salida
from tests.services.entorno_falso import EntornoFalso

CARPETA = "/resp/scripts_programados"
SCRIPT = f"{CARPETA}/diario.sh"


class EntornoConLogs(EntornoFalso):
    """Como EntornoFalso, pero cada archivo devuelve su propio contenido."""

    def __init__(self, contenidos=None, **kwargs):
        super().__init__(**kwargs)
        self.contenidos = contenidos or {}

    def leer_archivo(self, ruta):
        super().leer_archivo(ruta)
        if ruta not in self.contenidos:
            raise ArchivoNoLegible(str(ruta))
        return self.contenidos[ruta]


class EntornoWindows(EntornoConLogs):
    tipo_ruta = PureWindowsPath


def fila(ruta_script=SCRIPT, nombre="diario"):
    return rp.RespaldoProgramado(
        id=7, nombre=nombre, politica="FULL", frecuencia="DIARIO", hora="02:30", dia=None,
        intervalo_horas=None, directorio="DIR_RESP", ruta_script=ruta_script,
        ruta_rman=ruta_script.replace(".sh", ".rman"), entorno="local", tarea="OracleAdmin_7",
        creado=None, ultima_ejecucion=None, ultimo_resultado=None,
    )


class Consulta:
    def __init__(self, resultado):
        self.resultado = resultado
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        return self.resultado


class Sentencia:
    def __init__(self):
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))


def consulta_con(f):
    return Consulta([(f.id, f.nombre, f.politica, f.frecuencia, f.hora, f.dia, f.intervalo_horas,
                      f.directorio, f.ruta_script, f.ruta_rman, f.entorno, f.tarea, f.creado,
                      f.ultima_ejecucion, f.ultimo_resultado)])


def test_ejecutar_corre_el_script_guardado_y_registra_completo():
    entorno = EntornoConLogs(salidas_archivo={PurePosixPath(SCRIPT): Salida(0, "stdout")})
    consulta, sentencia = consulta_con(fila()), Sentencia()

    resultado = rp.ejecutar(consulta, sentencia, entorno, 7)

    assert entorno.ejecuciones == [PurePosixPath(SCRIPT)]
    assert consulta.llamadas[0][1] == {"id": 7}
    assert len(sentencia.llamadas) == 1
    sql, params = sentencia.llamadas[0]
    assert sql.startswith("UPDATE SYSTEM.RESPALDOS_PROGRAMADOS") and params == {"id": 7, "resultado": "Completo"}
    assert resultado == rp.ResultadoEjecucion(resultado="Completo", log="stdout")
    with pytest.raises(dataclasses.FrozenInstanceError):
        resultado.log = "x"


def test_ejecutar_devuelve_el_log_mas_reciente_de_esta_programacion():
    P = PurePosixPath
    archivos = [
        ArchivoEntorno("diario_20260101_020000.log", 10, 100.0),
        ArchivoEntorno("diario_20260103_020000.log", 10, 300.0),  # el más reciente
        ArchivoEntorno("diario_20260102_020000.log", 10, 200.0),
        ArchivoEntorno("diario2_20260104_020000.log", 10, 400.0),  # otra programación
        ArchivoEntorno("diario_20260104_020000.log.bak", 10, 500.0),  # otro archivo
        ArchivoEntorno("diario_20260104.log", 10, 600.0),  # sin marca de hora
        ArchivoEntorno("diario.rman", 10, 700.0),
    ]
    contenidos = {P(f"/resp/{a.nombre}"): a.nombre for a in archivos}
    entorno = EntornoConLogs(contenidos, archivos={P("/resp"): archivos}, texto="stdout")

    resultado = rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7)

    assert entorno.listados == [P("/resp")]
    assert entorno.lecturas == [P("/resp/diario_20260103_020000.log")]
    assert resultado.log == "diario_20260103_020000.log"


def test_ejecutar_desempata_por_modificado_y_no_distingue_mayusculas():
    P = PurePosixPath
    archivos = [
        ArchivoEntorno("diario_20260101_020000.log", 1, 100.0),
        ArchivoEntorno("DIARIO_20260101_020000.LOG", 1, 200.0),
    ]
    contenidos = {P(f"/resp/{a.nombre}"): a.nombre for a in archivos}
    entorno = EntornoConLogs(contenidos, archivos=archivos)

    assert rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7).log == "DIARIO_20260101_020000.LOG"


def test_ejecutar_el_nombre_se_escapa_en_la_busqueda_del_log():
    archivos = [ArchivoEntorno("dxario_20260101_020000.log", 1, 100.0)]
    entorno = EntornoConLogs({PurePosixPath("/resp/dxario_20260101_020000.log"): "ajeno"}, archivos=archivos, texto="stdout")

    assert rp.ejecutar(consulta_con(fila(f"{CARPETA}/d.x.sh", "d.x")), Sentencia(), entorno, 7).log == "stdout"


def test_ejecutar_sin_log_usa_la_salida_del_script():
    entorno = EntornoConLogs(archivos=[ArchivoEntorno("otro.log", 1, 1.0)], texto="stdout")
    assert rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7).log == "stdout"


def test_ejecutar_log_ilegible_usa_la_salida_del_script():
    entorno = EntornoConLogs(archivos=[ArchivoEntorno("diario_20260101_020000.log", 1, 1.0)], texto="stdout")
    assert rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7).log == "stdout"


def test_ejecutar_listado_fallido_usa_la_salida_del_script():
    entorno = EntornoConLogs(fallo_listado="sin acceso", texto="stdout")
    assert rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7).log == "stdout"


def test_ejecutar_variante_windows():
    ruta = r"C:\resp\scripts_programados\diario.bat"
    W = PureWindowsPath
    archivos = [
        ArchivoEntorno("diario_20260101_020000.log", 1, 100.0),
        ArchivoEntorno("diario_20260102_020000.log", 1, 200.0),
    ]
    contenidos = {W(rf"C:\resp\{a.nombre}"): a.nombre for a in archivos}
    entorno = EntornoWindows(contenidos, archivos={W(r"C:\resp"): archivos})

    resultado = rp.ejecutar(consulta_con(fila(ruta)), Sentencia(), entorno, 7)

    assert entorno.ejecuciones == [W(ruta)]
    assert resultado == rp.ResultadoEjecucion("Completo", "diario_20260102_020000.log")
