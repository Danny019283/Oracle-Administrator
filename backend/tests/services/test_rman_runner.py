from src.services.entorno_oracle import Salida
from src.services.rman_runner import ejecutar_rman
from tests.services.entorno_falso import RUTA_TEMPORAL, EntornoFalso

SCRIPT = "RUN {\n  BACKUP DATABASE;\n}\n"


def test_pide_al_entorno_rman_con_autenticacion_del_so_y_cmdfile_temporal():
    entorno = EntornoFalso()

    ejecutar_rman(entorno, SCRIPT, "XE")

    assert entorno.herramientas == [
        {
            "nombre": "rman",
            "args": ["target", "/", f"cmdfile={RUTA_TEMPORAL}"],
            "script": SCRIPT,
            "prefijo": "rman",
            "extension": ".rman",
            "variables": {"ORACLE_SID": "XE"},
        }
    ]


def test_pone_el_sid_recibido_en_oracle_sid():
    entorno = EntornoFalso()

    ejecutar_rman(entorno, SCRIPT, "ORCL")

    assert entorno.herramientas[0]["variables"] == {"ORACLE_SID": "ORCL"}


def test_devuelve_la_salida_de_rman():
    salida = ejecutar_rman(EntornoFalso(codigo=3, texto="salida de rman"), SCRIPT, "XE")

    assert salida == Salida(codigo=3, texto="salida de rman")
