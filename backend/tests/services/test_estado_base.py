import pytest

from src.services.entorno_oracle import HerramientaNoDisponible, Salida
from src.services.estado_base import (
    ABIERTA,
    APAGADA,
    MOUNT,
    NOMOUNT,
    AccionNoValida,
    EstadoBaseFallido,
    cambiar_estado,
    estado_actual,
)
from tests.services.entorno_falso import EntornoFalso

CONSULTA = "SELECT status FROM v$instance;"
ESTADOS = {"STARTED": NOMOUNT, "MOUNTED": MOUNT, "OPEN": ABIERTA}


def sentencias(herramienta):
    return [linea.strip() for linea in herramienta["script"].splitlines() if linea.strip()]


def entorno_en(estado, codigo_accion=0, texto_accion="hecho"):
    texto = {NOMOUNT: "STARTED", MOUNT: "MOUNTED", ABIERTA: "OPEN"}.get(estado)
    consulta = (
        Salida(0, f"\n{texto}\n")
        if texto
        else Salida(1, "ERROR:\nORA-01034: ORACLE not available\n")
    )
    return EntornoFalso(salidas=[consulta, Salida(codigo_accion, texto_accion)])


@pytest.mark.parametrize("status,estado", ESTADOS.items())
def test_traduce_el_status_de_v_instance_al_estado(status, estado):
    entorno = EntornoFalso(texto=f"\n{status}\n")

    assert estado_actual(entorno, "XE") == estado


@pytest.mark.parametrize("codigo", ["ORA-01034", "ORA-12162"])
def test_si_la_instancia_no_responde_el_estado_es_apagada_aunque_sqlplus_devuelva_0(codigo):
    entorno = EntornoFalso(codigo=0, texto=f"ERROR:\n{codigo}: no responde\n")

    assert estado_actual(entorno, "XE") == APAGADA


def test_la_consulta_usa_sqlplus_como_sysdba_con_script_fijo_y_el_sid():
    entorno = EntornoFalso(texto="OPEN")

    estado_actual(entorno, "ORCL")

    herramienta = entorno.herramientas[0]
    assert herramienta["nombre"] == "sqlplus"
    assert herramienta["args"][:2] == ["-S", "/ as sysdba"]
    assert herramienta["args"][2].startswith("@")
    assert CONSULTA in sentencias(herramienta)
    assert herramienta["variables"] == {"ORACLE_SID": "ORCL"}


def test_sqlplus_con_otro_error_lanza_estado_fallido_con_log_y_explicacion():
    entorno = EntornoFalso(codigo=1, texto="ORA-01031: insufficient privileges")

    with pytest.raises(EstadoBaseFallido) as error:
        estado_actual(entorno, "XE")

    assert error.value.log == "ORA-01031: insufficient privileges"
    assert "privilegio" in error.value.explicacion


def test_una_salida_sin_estado_reconocible_lanza_estado_fallido():
    with pytest.raises(EstadoBaseFallido):
        estado_actual(EntornoFalso(texto="algo raro"), "XE")


def test_herramienta_no_disponible_se_deja_pasar():
    class SinSqlplus(EntornoFalso):
        def ejecutar(self, comando):
            raise HerramientaNoDisponible("sqlplus")

    with pytest.raises(HerramientaNoDisponible):
        estado_actual(SinSqlplus(), "XE")


TRANSICIONES = [
    ("APAGAR", NOMOUNT, ["SHUTDOWN IMMEDIATE"]),
    ("APAGAR", MOUNT, ["SHUTDOWN IMMEDIATE"]),
    ("APAGAR", ABIERTA, ["SHUTDOWN IMMEDIATE"]),
    ("NOMOUNT", APAGADA, ["STARTUP NOMOUNT"]),
    ("MOUNT", APAGADA, ["STARTUP MOUNT"]),
    ("MOUNT", NOMOUNT, ["ALTER DATABASE MOUNT;"]),
    ("ENCENDER", APAGADA, ["STARTUP"]),
    ("ENCENDER", NOMOUNT, ["ALTER DATABASE MOUNT;", "ALTER DATABASE OPEN;"]),
    ("ENCENDER", MOUNT, ["ALTER DATABASE OPEN;"]),
]


@pytest.mark.parametrize("accion,estado,esperadas", TRANSICIONES)
def test_transicion_valida_ejecuta_el_script_fijo_de_la_accion(accion, estado, esperadas):
    entorno = entorno_en(estado)

    log = cambiar_estado(entorno, "XE", accion)

    assert len(entorno.herramientas) == 2
    herramienta = entorno.herramientas[1]
    assert herramienta["nombre"] == "sqlplus"
    assert herramienta["args"][:2] == ["-S", "/ as sysdba"]
    assert herramienta["variables"] == {"ORACLE_SID": "XE"}
    assert sentencias(herramienta) == ["WHENEVER SQLERROR EXIT SQL.SQLCODE", *esperadas, "EXIT"]
    assert log == "hecho"


INVALIDAS = [
    ("APAGAR", APAGADA),
    ("NOMOUNT", NOMOUNT),
    ("NOMOUNT", MOUNT),
    ("NOMOUNT", ABIERTA),
    ("MOUNT", MOUNT),
    ("MOUNT", ABIERTA),
    ("ENCENDER", ABIERTA),
    ("REINICIAR", APAGADA),
]


@pytest.mark.parametrize("accion,estado", INVALIDAS)
def test_accion_no_valida_para_el_estado_no_ejecuta_nada_mas_que_la_consulta(accion, estado):
    entorno = entorno_en(estado)

    with pytest.raises(AccionNoValida):
        cambiar_estado(entorno, "XE", accion)

    assert len(entorno.herramientas) == 1


def test_sqlplus_con_codigo_distinto_de_cero_lanza_fallo_con_log_y_explicacion():
    entorno = entorno_en(APAGADA, codigo_accion=1, texto_accion="ORA-01031: insufficient privileges")

    with pytest.raises(EstadoBaseFallido) as error:
        cambiar_estado(entorno, "XE", "ENCENDER")

    assert error.value.log == "ORA-01031: insufficient privileges"
    assert "privilegio" in error.value.explicacion
