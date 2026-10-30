from datetime import datetime
from pathlib import PurePosixPath

from src.services.archivos_respaldo import agrupar_archivos, listar_respaldos
from src.services.entorno_oracle import ArchivoEntorno
import pytest

from src.services.archivos_respaldo import RespaldoInvalido
from src.services.identificadores import IdentificadorInvalido
from src.services.recuperacion import nombre_log_recuperacion, validar_solicitud_datapump
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


# --- Validación de la solicitud Data Pump (FA-4b, RN-4, RN-5) ---


def test_tablas_se_normalizan_a_owner_tabla_en_mayusculas():
    assert validar_solicitud_datapump("tablas", ["hr.employees", " Scott.Emp "], "SKIP") == (
        ["HR.EMPLOYEES", "SCOTT.EMP"],
        "SKIP",
    )


def test_schemas_se_normalizan_y_existentes_es_skip_por_defecto():
    assert validar_solicitud_datapump("schemas", ["hr", "scott"]) == (["HR", "SCOTT"], "SKIP")


@pytest.mark.parametrize("accion", ["SKIP", "APPEND", "TRUNCATE", "REPLACE"])
def test_acepta_las_cuatro_acciones_sobre_tablas_existentes(accion):
    assert validar_solicitud_datapump("schemas", ["hr"], accion)[1] == accion


def test_modo_distinto_de_tablas_o_schemas_es_invalido():
    with pytest.raises(RespaldoInvalido, match="El modo debe ser Tablas o Schemas"):
        validar_solicitud_datapump("full", ["hr"])


@pytest.mark.parametrize("objetos", [[], None])
def test_objetos_vacios_son_invalidos(objetos):
    with pytest.raises(RespaldoInvalido, match="Debes indicar al menos un objeto"):
        validar_solicitud_datapump("schemas", objetos)


@pytest.mark.parametrize("accion", ["DROP", "skip", "", None])
def test_accion_sobre_existentes_desconocida_es_invalida(accion):
    with pytest.raises(RespaldoInvalido, match="La acción sobre tablas existentes debe ser"):
        validar_solicitud_datapump("schemas", ["hr"], accion)


@pytest.mark.parametrize("tabla", ["EMPLOYEES", "HR.", ".EMP", "HR.EMP.X", "HR.EMP;DROP", "1HR.EMP"])
def test_tabla_que_no_es_owner_tabla_valido_es_invalida(tabla):
    with pytest.raises((RespaldoInvalido, IdentificadorInvalido)):
        validar_solicitud_datapump("tablas", [tabla])


@pytest.mark.parametrize("schema", ["", "HR.EMP", "HR;DROP", "1HR", 'HR"'])
def test_schema_invalido_lanza_identificador_invalido(schema):
    with pytest.raises(IdentificadorInvalido):
        validar_solicitud_datapump("schemas", [schema])
