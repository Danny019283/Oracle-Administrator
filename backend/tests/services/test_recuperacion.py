from datetime import datetime
from pathlib import PurePosixPath

from src.services.archivos_respaldo import agrupar_archivos, listar_respaldos
from src.services.entorno_oracle import ArchivoEntorno
from src.services.recuperacion import nombre_log_recuperacion
from tests.services.entorno_falso import EntornoFalso

BASE = "hr_20240105_103000"
LOG = "hr_20240105_103000_recuperacion_20240601-094507.log"


def _a(nombre: str, tamano: int = 1) -> ArchivoEntorno:
    return ArchivoEntorno(nombre=nombre, tamano=tamano, modificado=0.0)


class _Consulta:
    def __call__(self, sql, params=None):
        return [("RESPALDO", "/a")]


def test_nombre_log_recuperacion_lleva_fecha_y_hora_con_guion():
    assert nombre_log_recuperacion(BASE, datetime(2024, 6, 1, 9, 45, 7)) == LOG


def test_log_de_recuperacion_no_es_respaldo_ni_se_suma_a_su_base():
    r = agrupar_archivos([_a(f"{BASE}.dmp", 100), _a(f"{BASE}.log", 5), _a(LOG, 7)])

    assert [(x.base, x.tamano) for x in r] == [(BASE, 105)]
    assert LOG not in {a.nombre for a in r[0].archivos}


def test_listar_respaldos_ignora_el_log_de_recuperacion_y_no_cambia_el_estado():
    entorno = EntornoFalso(
        log="successfully completed",
        archivos={PurePosixPath("/a"): [_a(f"{BASE}.dmp"), _a(f"{BASE}.log"), _a(LOG)]},
    )

    respaldos, avisos = listar_respaldos(_Consulta(), entorno)

    assert [(r.base, r.estado) for r in respaldos] == [(BASE, "Completo")]
    assert avisos == []
