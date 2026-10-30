from datetime import datetime

from pathlib import PurePosixPath

import pytest

from src.services.archivos_respaldo import (
    RespaldoInvalido,
    RespaldoNoEncontrado,
    ResultadoEliminacion,
    agrupar_archivos,
    eliminar_respaldo,
    estado_de,
    listar_respaldos,
)
from src.services.directorios import DirectorioNoEncontrado
from src.services.entorno_oracle import ArchivoEntorno, HerramientaNoDisponible, OperacionEntornoFallida
from tests.services.entorno_falso import EntornoFalso

SID = "XE"


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


class _Consulta:
    def __init__(self, filas):
        self.filas = filas

    def __call__(self, sql, params=None):
        return self.filas


class _EntornoQueNoLee(EntornoFalso):
    def __init__(self, ilegibles, **kw):
        super().__init__(**kw)
        self.ilegibles = ilegibles

    def listar_archivos(self, ruta):
        if ruta in self.ilegibles:
            raise OperacionEntornoFallida("Permission denied")
        return super().listar_archivos(ruta)


def test_sin_directorios_devuelve_dos_listas_vacias():
    assert listar_respaldos(_Consulta([]), EntornoFalso()) == ([], [])


def test_respaldos_de_varios_directorios_con_directorio_ruta_estado_y_orden_global():
    entorno = EntornoFalso(
        log="successfully completed",
        archivos={
            PurePosixPath("/a"): [_a("a_20240101_000000.dmp"), _a("a_20240101_000000.log")],
            PurePosixPath("/dp"): [_a("z_20240301_000000.dmp"), _a("q_20240201_000000.dmp")],
        },
    )

    respaldos, avisos = listar_respaldos(
        _Consulta([("RESPALDO", "/a"), ("DATA_PUMP_DIR", "/dp")]), entorno
    )

    assert avisos == []
    assert [(r.base, r.directorio, r.ruta, r.estado) for r in respaldos] == [
        ("z_20240301_000000", "DATA_PUMP_DIR", "/dp", "Sin log"),
        ("q_20240201_000000", "DATA_PUMP_DIR", "/dp", "Sin log"),
        ("a_20240101_000000", "RESPALDO", "/a", "Completo"),
    ]
    assert entorno.listados == [PurePosixPath("/a"), PurePosixPath("/dp")]


def test_directorio_ilegible_se_omite_con_aviso_y_los_demas_siguen():
    entorno = _EntornoQueNoLee(
        {PurePosixPath("/mal")},
        archivos=[_a("a_20240101_000000.dmp")],
    )

    respaldos, avisos = listar_respaldos(_Consulta([("ROTO", "/mal"), ("BIEN", "/ok")]), entorno)

    assert [(r.base, r.directorio) for r in respaldos] == [("a_20240101_000000", "BIEN")]
    assert len(avisos) == 1
    assert "ROTO" in avisos[0]


def test_directorios_internos_de_oracle_ocm_se_ignoran_sin_listar_ni_avisar():
    entorno = _EntornoQueNoLee({PurePosixPath("/ocm"), PurePosixPath("/ocm2")})

    respaldos, avisos = listar_respaldos(
        _Consulta([("ORACLE_OCM_CONFIG_DIR", "/ocm"), ("ORACLE_OCM_CONFIG_DIR2", "/ocm2")]), entorno
    )

    assert (respaldos, avisos) == ([], [])
    assert entorno.listados == []


def test_directorio_de_sistema_ilegible_distinto_de_ocm_sigue_con_aviso_y_los_legibles_se_listan():
    entorno = _EntornoQueNoLee(
        {PurePosixPath("/dp"), PurePosixPath("/ocm")}, archivos=[_a("a_20240101_000000.dmp")]
    )

    respaldos, avisos = listar_respaldos(
        _Consulta([("DATA_PUMP_DIR", "/dp"), ("ORACLE_OCM_CONFIG_DIR", "/ocm"), ("OTRO", "/otro")]), entorno
    )

    assert len(avisos) == 1 and "DATA_PUMP_DIR" in avisos[0]
    assert [r.directorio for r in respaldos] == ["OTRO"]
    assert entorno.listados == [PurePosixPath("/otro")]


def test_data_pump_dir_legible_sigue_en_la_lista():
    entorno = EntornoFalso(archivos={PurePosixPath("/dp"): [_a("a_20240101_000000.dmp")]})

    respaldos, avisos = listar_respaldos(_Consulta([("DATA_PUMP_DIR", "/dp")]), entorno)

    assert avisos == []
    assert [r.directorio for r in respaldos] == ["DATA_PUMP_DIR"]


_DIRS = _Consulta([("RESPALDO", "/a"), ("DATA_PUMP_DIR", "/dp")])


def _entorno_con(archivos: dict[str, list[ArchivoEntorno]], **kw) -> EntornoFalso:
    return EntornoFalso(archivos={PurePosixPath(k): v for k, v in archivos.items()}, **kw)


def test_borra_el_dump_y_su_log_y_devuelve_el_tipo():
    entorno = _entorno_con(
        {"/a": [_a("a_20240101_000000.dmp"), _a("a_20240101_000000.log")]}
    )

    resultado = eliminar_respaldo(_DIRS, entorno, "respaldo", "a_20240101_000000", SID)

    assert resultado == ResultadoEliminacion("Data Pump")
    assert sorted(entorno.borrados) == [
        PurePosixPath("/a/a_20240101_000000.dmp"),
        PurePosixPath("/a/a_20240101_000000.log"),
    ]


def test_borra_las_piezas_del_full_rman_y_su_log():
    entorno = _entorno_con(
        {
            "/a": [
                _a("f_20240101_000000_ORCL_1_1.dbf"),
                _a("f_20240101_000000_ORCL_2_1.dbf"),
                _a("f_20240101_000000.log"),
            ]
        }
    )

    resultado = eliminar_respaldo(_DIRS, entorno, "RESPALDO", "f_20240101_000000", SID)

    assert resultado.tipo == "RMAN"
    assert sorted(entorno.borrados) == [
        PurePosixPath("/a/f_20240101_000000.log"),
        PurePosixPath("/a/f_20240101_000000_ORCL_1_1.dbf"),
        PurePosixPath("/a/f_20240101_000000_ORCL_2_1.dbf"),
    ]


def test_no_toca_otras_bases_ni_archivos_ajenos():
    entorno = _entorno_con(
        {
            "/a": [
                _a("a_20240101_000000.dmp"),
                _a("a_20240101_000000.log"),
                _a("b_20240202_000000.dmp"),
                _a("a_20240101_000000.txt"),
                _a("notas.txt"),
            ]
        }
    )

    eliminar_respaldo(_DIRS, entorno, "RESPALDO", "a_20240101_000000", SID)

    assert sorted(entorno.borrados) == [
        PurePosixPath("/a/a_20240101_000000.dmp"),
        PurePosixPath("/a/a_20240101_000000.log"),
    ]


@pytest.mark.parametrize(
    "base",
    [
        "../x_20240101_120000",
        "a/b_20240101_120000",
        "a_20240101_120000.dmp",
        "a_20240101",
        "",
        "a_20240101_120000\n",
    ],
)
def test_base_invalida_no_borra_nada(base):
    entorno = _entorno_con({"/a": [_a("a_20240101_000000.dmp")]})

    with pytest.raises(RespaldoInvalido):
        eliminar_respaldo(_DIRS, entorno, "RESPALDO", base, SID)

    assert entorno.borrados == []


@pytest.mark.parametrize("nombre", ["NOEXISTE", "../etc", ""])
def test_directorio_inexistente(nombre):
    entorno = _entorno_con({"/a": [_a("a_20240101_000000.dmp")]})

    with pytest.raises(DirectorioNoEncontrado):
        eliminar_respaldo(_DIRS, entorno, nombre, "a_20240101_000000", SID)

    assert entorno.borrados == []


def test_respaldo_inexistente():
    entorno = _entorno_con({"/a": [_a("a_20240101_000000.dmp")]})

    with pytest.raises(RespaldoNoEncontrado, match="Respaldo no encontrado"):
        eliminar_respaldo(_DIRS, entorno, "RESPALDO", "z_20240909_000000", SID)

    assert entorno.borrados == []


def test_directorio_de_sistema_se_permite():
    entorno = _entorno_con({"/dp": [_a("a_20240101_000000.dmp")]})

    resultado = eliminar_respaldo(_DIRS, entorno, "data_pump_dir", "a_20240101_000000", SID)
    assert resultado.tipo == "Data Pump"
    assert entorno.borrados == [PurePosixPath("/dp/a_20240101_000000.dmp")]


class _EntornoQueFallaAlSegundo(EntornoFalso):
    def borrar_archivo(self, ruta):
        super().borrar_archivo(ruta)
        if len(self.borrados) == 2:
            raise OperacionEntornoFallida("rm: Permission denied")


def test_fallo_de_borrado_se_propaga_y_no_intenta_los_siguientes():
    entorno = _EntornoQueFallaAlSegundo(
        archivos=[
            _a("a_20240101_000000.dmp"),
            _a("a_20240101_000000.log"),
            _a("a_20240101_000000_ORCL_1_1.dbf"),
        ]
    )

    with pytest.raises(OperacionEntornoFallida, match="Permission denied"):
        eliminar_respaldo(_Consulta([("RESPALDO", "/a")]), entorno, "RESPALDO", "a_20240101_000000", SID)

    assert len(entorno.borrados) == 2


_RMAN = [_a("f_20240101_000000_ORCL_1_1.dbf"), _a("f_20240101_000000.log")]
_LIMPIEZA = "CROSSCHECK BACKUP;\nDELETE NOPROMPT EXPIRED BACKUP;\n"


def test_rman_ejecuta_el_script_fijo_de_limpieza_con_el_sid_y_sin_advertencia():
    entorno = _entorno_con({"/a": _RMAN})

    resultado = eliminar_respaldo(_DIRS, entorno, "RESPALDO", "f_20240101_000000", "ORCL")

    assert resultado == ResultadoEliminacion("RMAN")
    assert [(h["nombre"], h["script"], h["variables"]) for h in entorno.herramientas] == [
        ("rman", _LIMPIEZA, {"ORACLE_SID": "ORCL"})
    ]


def test_data_pump_no_ejecuta_rman():
    entorno = _entorno_con({"/a": [_a("a_20240101_000000.dmp"), _a("a_20240101_000000.log")]})

    eliminar_respaldo(_DIRS, entorno, "RESPALDO", "a_20240101_000000", SID)

    assert entorno.herramientas == []


def test_fallo_de_rman_devuelve_advertencia_y_los_archivos_siguen_borrados():
    entorno = _entorno_con({"/a": _RMAN}, codigo=1, texto="RMAN-06059: falta un archivelog")

    resultado = eliminar_respaldo(_DIRS, entorno, "RESPALDO", "f_20240101_000000", SID)

    assert resultado.tipo == "RMAN"
    assert resultado.advertencia.log == "RMAN-06059: falta un archivelog"
    assert "Faltan archivelogs" in resultado.advertencia.explicacion
    assert len(entorno.borrados) == 2


class _EntornoSinRman(EntornoFalso):
    def ejecutar(self, comando):
        raise HerramientaNoDisponible(comando.nombre)


def test_rman_no_disponible_es_advertencia_y_no_pierde_el_borrado():
    entorno = _EntornoSinRman(archivos={PurePosixPath("/a"): _RMAN})

    resultado = eliminar_respaldo(_DIRS, entorno, "RESPALDO", "f_20240101_000000", SID)

    assert resultado.advertencia is not None
    assert len(entorno.borrados) == 2


def test_si_falla_el_borrado_de_archivos_no_se_ejecuta_rman():
    entorno = _entorno_con({"/a": _RMAN}, fallo_borrado="rm: Permission denied")

    with pytest.raises(OperacionEntornoFallida):
        eliminar_respaldo(_DIRS, entorno, "RESPALDO", "f_20240101_000000", SID)

    assert entorno.herramientas == []
