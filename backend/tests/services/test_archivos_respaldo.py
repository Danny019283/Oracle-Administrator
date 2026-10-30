from datetime import datetime

from pathlib import PurePosixPath

from src.services.archivos_respaldo import agrupar_archivos, estado_de
from src.services.entorno_oracle import ArchivoEntorno
from tests.services.entorno_falso import EntornoFalso


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


RUTA = "/backups"


def _estado(archivos: list[str], log: str | None) -> tuple[str, EntornoFalso]:
    entorno = EntornoFalso(log=log)
    (respaldo,) = agrupar_archivos([_a(n) for n in archivos])
    return estado_de(respaldo, entorno, RUTA), entorno


DUMP = ["hr_20240105_103000.dmp", "hr_20240105_103000.log"]
RMAN = ["hr_20240105_103000_ORCL_7_1.dbf", "hr_20240105_103000.log"]


def test_data_pump_con_successfully_completed_esta_completo():
    estado, entorno = _estado(DUMP, "Job successfully completed at 10:31")

    assert estado == "Completo"
    assert entorno.lecturas == [PurePosixPath(RUTA) / "hr_20240105_103000.log"]


def test_rman_con_finished_backup_esta_completo():
    assert _estado(RMAN, "Finished backup at 05-JAN-24")[0] == "Completo"


def test_ora_o_rman_en_el_log_prevalece_sobre_el_exito():
    assert _estado(DUMP, "ORA-39002: invalid operation\nsuccessfully completed")[0] == "Con errores"
    assert _estado(RMAN, "RMAN-03009: failure\nFinished backup")[0] == "Con errores"


def test_log_sin_errores_ni_marca_de_exito_cuenta_como_sin_log():
    assert _estado(DUMP, "Export: Release 19.0")[0] == "Sin log"


def test_marca_de_exito_de_otro_tipo_no_cuenta():
    assert _estado(DUMP, "Finished backup")[0] == "Sin log"
    assert _estado(RMAN, "successfully completed")[0] == "Sin log"


def test_log_ilegible_es_sin_log():
    assert _estado(DUMP, None)[0] == "Sin log"


def test_sin_archivo_log_es_sin_log_y_no_se_intenta_leer():
    estado, entorno = _estado(["hr_20240105_103000.dmp"], "successfully completed")

    assert estado == "Sin log"
    assert entorno.lecturas == []


def test_solo_log_es_sin_respaldo():
    assert _estado(["hr_20240105_103000.log"], "successfully completed")[0] == "Sin respaldo"


def test_solo_log_con_errores_prevalece_el_error():
    assert _estado(["hr_20240105_103000.log"], "ORA-00001")[0] == "Con errores"
