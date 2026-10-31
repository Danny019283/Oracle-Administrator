from pathlib import PurePosixPath

import pytest

from src.services import respaldos_programados as rp
from src.services.entorno_oracle import ArchivoEntorno, HerramientaNoDisponible, OperacionEntornoFallida
from src.services.errores_oracle import explicar_error
from src.services.respaldo import RespaldoFallido
from tests.services.entorno_falso import EntornoFalso
from tests.services.test_respaldos_programados_ejecutar import (
    CARPETA,
    Consulta,
    Sentencia,
    consulta_con,
    fila,
    scripts_programados,
)

P = PurePosixPath
LOG_RMAN = "RMAN-00571: ===\nRMAN-03002: failure of backup command\nORA-19809: limit exceeded"


class EntornoConEventos(EntornoFalso):
    """Anota en `eventos` cuándo se lee un log, para comprobar el orden con el UPDATE."""

    def __init__(self, eventos, **kwargs):
        super().__init__(**kwargs)
        self.eventos = eventos

    def leer_archivo(self, ruta):
        self.eventos.append("log")
        return super().leer_archivo(ruta)


class SentenciaConEventos(Sentencia):
    def __init__(self, eventos):
        super().__init__()
        self.eventos = eventos

    def __call__(self, sql, params=None):
        self.eventos.append("UPDATE")
        super().__call__(sql, params)


def test_programacion_inexistente_no_ejecuta_ni_toca_la_tabla():
    entorno, sentencia = EntornoFalso(), Sentencia()

    with pytest.raises(rp.ProgramacionNoEncontrada):
        rp.ejecutar(Consulta([]), sentencia, entorno, 99)

    assert entorno.ejecuciones == [] and entorno.listados == []
    assert sentencia.llamadas == []


def test_script_ausente_en_disco_sugiere_reinstalar_sin_ejecutar_ni_actualizar():
    entorno = EntornoFalso(archivos={P(CARPETA): [ArchivoEntorno("otro.sh", 1, 1.0)]})
    sentencia = Sentencia()

    with pytest.raises(rp.ScriptNoEncontrado) as error:
        rp.ejecutar(consulta_con(fila()), sentencia, entorno, 7)

    assert "Reinstalar tareas" in str(error.value)
    assert entorno.listados == [P(CARPETA)]
    assert entorno.ejecuciones == []
    assert sentencia.llamadas == []


def test_fallo_al_listar_la_carpeta_del_script_se_propaga_sin_ejecutar_ni_actualizar():
    entorno = EntornoFalso(fallo_listado="sin acceso")
    sentencia = Sentencia()

    with pytest.raises(OperacionEntornoFallida):
        rp.ejecutar(consulta_con(fila()), sentencia, entorno, 7)

    assert entorno.ejecuciones == []
    assert sentencia.llamadas == []


def test_rman_con_error_lee_el_log_actualiza_con_errores_y_despues_lanza():
    eventos = []
    log = ArchivoEntorno("diario_20260101_020000.log", 1, 100.0)
    entorno = EntornoConEventos(
        eventos, codigo=1, texto="stdout",
        archivos={P(CARPETA): scripts_programados, P("/resp"): [log]}, log=LOG_RMAN,
    )
    sentencia = SentenciaConEventos(eventos)

    with pytest.raises(RespaldoFallido) as error:
        rp.ejecutar(consulta_con(fila()), sentencia, entorno, 7)

    assert eventos == ["log", "UPDATE"]
    sql, params = sentencia.llamadas[0]
    assert sql.startswith("UPDATE SYSTEM.RESPALDOS_PROGRAMADOS") and params == {"id": 7, "resultado": "Con errores"}
    assert error.value.codigo == 1
    assert error.value.log == LOG_RMAN
    assert error.value.explicacion == explicar_error(LOG_RMAN)
    assert "rman" in str(error.value)


def test_rman_con_error_sin_log_usa_la_salida_del_script():
    entorno = EntornoFalso(codigo=2, texto=LOG_RMAN, archivos=scripts_programados)

    with pytest.raises(RespaldoFallido) as error:
        rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7)

    assert (error.value.codigo, error.value.log) == (2, LOG_RMAN)


def test_herramienta_ausente_se_propaga_sin_actualizar_la_fila():
    entorno = EntornoFalso(archivos=scripts_programados, herramienta_ausente="sh")
    sentencia = Sentencia()

    with pytest.raises(HerramientaNoDisponible):
        rp.ejecutar(consulta_con(fila()), sentencia, entorno, 7)

    assert sentencia.llamadas == []


def test_reloj_acota_el_log_a_los_creados_desde_el_inicio():
    entorno = EntornoFalso(
        archivos={
            P(CARPETA): scripts_programados,
            P("/resp"): [
                ArchivoEntorno("diario_20260103_020000.log", 1, 100.0),  # de una ejecución anterior, aunque de nombre mayor
                ArchivoEntorno("diario_20260101_020000.log", 1, 996.0),  # dentro de la tolerancia de 5 s
            ],
        },
        texto="stdout", log="contenido",
    )

    resultado = rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7, reloj=lambda: 1000.0)

    assert entorno.lecturas == [P("/resp/diario_20260101_020000.log")]
    assert resultado.log == "contenido"


def test_reloj_ignora_el_log_viejo_y_usa_la_salida_del_script():
    entorno = EntornoFalso(
        archivos={P(CARPETA): scripts_programados, P("/resp"): [ArchivoEntorno("diario_20260101_020000.log", 1, 100.0)]},
        texto="stdout", log="viejo",
    )

    resultado = rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7, reloj=lambda: 1000.0)

    assert entorno.lecturas == []
    assert resultado.log == "stdout"


def test_sin_reloj_no_se_acota_y_se_usa_el_log_viejo():
    entorno = EntornoFalso(
        archivos={P(CARPETA): scripts_programados, P("/resp"): [ArchivoEntorno("diario_20260101_020000.log", 1, 100.0)]},
        texto="stdout", log="viejo",
    )

    assert rp.ejecutar(consulta_con(fila()), Sentencia(), entorno, 7).log == "viejo"


def test_reloj_se_lee_antes_de_ejecutar_el_script():
    eventos = []

    class Entorno(EntornoFalso):
        def ejecutar_archivo(self, ruta):
            eventos.append("ejecutar")
            return super().ejecutar_archivo(ruta)

    def reloj():
        eventos.append("reloj")
        return 0.0

    rp.ejecutar(consulta_con(fila()), Sentencia(), Entorno(archivos=scripts_programados), 7, reloj=reloj)

    assert eventos == ["reloj", "ejecutar"]
