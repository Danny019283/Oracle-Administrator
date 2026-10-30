from datetime import datetime

from src.services.archivos_respaldo import agrupar_archivos
from src.services.entorno_oracle import ArchivoEntorno


def _a(nombre: str, tamano: int = 1) -> ArchivoEntorno:
    return ArchivoEntorno(nombre=nombre, tamano=tamano, modificado=0.0)


def test_dump_y_log_forman_un_respaldo_data_pump():
    r = agrupar_archivos(
        [_a("hr_20240105_103000.dmp", 100), _a("hr_20240105_103000.log", 5)]
    )

    assert len(r) == 1
    assert r[0].base == "hr_20240105_103000"
    assert r[0].tipo == "Data Pump"
    assert r[0].tamano == 105
    assert r[0].fecha == datetime(2024, 1, 5, 10, 30, 0)
    assert {a.nombre for a in r[0].archivos} == {
        "hr_20240105_103000.dmp",
        "hr_20240105_103000.log",
    }


def test_full_rman_con_varias_piezas_y_log_es_un_solo_respaldo():
    r = agrupar_archivos(
        [
            _a("full_20240105_103000_ORCL_7_1.dbf", 10),
            _a("full_20240105_103000_ORCL_7_2.dbf", 20),
            _a("full_20240105_103000_ORCL_8_1.dbf", 30),
            _a("full_20240105_103000.log", 1),
        ]
    )

    assert len(r) == 1
    assert r[0].base == "full_20240105_103000"
    assert r[0].tipo == "RMAN"
    assert r[0].tamano == 61
    assert len(r[0].archivos) == 4


def test_dos_bases_se_ordenan_de_la_mas_reciente_a_la_mas_antigua():
    r = agrupar_archivos(
        [
            _a("a_20240101_000000.dmp"),
            _a("b_20240301_000000.dmp"),
            _a("c_20240201_000000.dmp"),
        ]
    )

    assert [x.base for x in r] == [
        "b_20240301_000000",
        "c_20240201_000000",
        "a_20240101_000000",
    ]


def test_log_solo_es_de_tipo_desconocido():
    r = agrupar_archivos([_a("x_20240105_103000.log")])

    assert [(x.base, x.tipo) for x in r] == [("x_20240105_103000", "Desconocido")]


def test_archivos_ajenos_se_ignoran():
    r = agrupar_archivos(
        [
            _a("notas.txt"),
            _a("hr_20240105_103000.txt"),
            _a("hr.dmp"),
            _a("hr_20240105.dmp"),
            _a("hr_20241305_103000.dmp"),
            _a("hr_20240105_103000_ORCL.dbf"),
            _a("hr_20240105_103000.dmp.bak"),
        ]
    )

    assert r == []


def test_nombre_con_guiones_bajos_y_numeros_no_confunde_la_pieza_rman():
    r = agrupar_archivos(
        [
            _a("mi_2_20240101_120000_20240102_130000_ORCL_12_3.dbf", 7),
            _a("mi_2_20240101_120000_20240102_130000.log", 1),
            _a("mi_2_20240101_120000.dmp", 50),
        ]
    )

    por_base = {x.base: x for x in r}
    assert set(por_base) == {
        "mi_2_20240101_120000_20240102_130000",
        "mi_2_20240101_120000",
    }
    rman = por_base["mi_2_20240101_120000_20240102_130000"]
    assert (rman.tipo, rman.tamano) == ("RMAN", 8)
    assert rman.fecha == datetime(2024, 1, 2, 13, 0, 0)
    assert por_base["mi_2_20240101_120000"].tipo == "Data Pump"
