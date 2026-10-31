import pytest

from src.services.entorno_oracle import HerramientaNoDisponible
from src.services.respaldo import RespaldoFallido
from src.services.respaldos_programados import aplicar_politica_global
from tests.services.entorno_falso import EntornoFalso

SCRIPT = (
    "CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 7 DAYS;\n"
    "CONFIGURE BACKUP OPTIMIZATION ON;\n"
    "CONFIGURE CONTROLFILE AUTOBACKUP ON;\n"
)


def test_envia_el_script_fijo_con_el_sid_y_sin_log():
    entorno = EntornoFalso()

    assert aplicar_politica_global(entorno, "XE") is None

    assert len(entorno.herramientas) == 1
    ejecucion = entorno.herramientas[0]
    assert ejecucion["nombre"] == "rman"
    assert ejecucion["script"] == SCRIPT
    assert ejecucion["variables"] == {"ORACLE_SID": "XE"}
    assert not any(a.startswith("log=") for a in ejecucion["args"])


def test_repetirla_manda_el_mismo_script():
    entorno = EntornoFalso()

    aplicar_politica_global(entorno, "XE")
    aplicar_politica_global(entorno, "XE")

    assert [h["script"] for h in entorno.herramientas] == [SCRIPT, SCRIPT]


def test_codigo_distinto_de_cero_lanza_error_con_codigo_log_y_explicacion():
    entorno = EntornoFalso(codigo=1, texto="RMAN-03002: failure of configure command\nORA-19809: limit")

    with pytest.raises(RespaldoFallido) as error:
        aplicar_politica_global(entorno, "XE")

    assert error.value.codigo == 1
    assert "RMAN-03002" in error.value.log
    assert error.value.explicacion


def test_rman_ausente_deja_pasar_herramienta_no_disponible():
    class SinRman(EntornoFalso):
        def ejecutar(self, comando):
            raise HerramientaNoDisponible("rman")

    with pytest.raises(HerramientaNoDisponible):
        aplicar_politica_global(SinRman(), "XE")
