from datetime import datetime
from pathlib import PurePosixPath

from src.services.archivos_respaldo import agrupar_archivos, listar_respaldos
from src.services.entorno_oracle import ArchivoEntorno
import pytest

from src.services.archivos_respaldo import RespaldoInvalido, RespaldoNoEncontrado
from src.services.directorios import DirectorioNoEncontrado
from src.services.entorno_oracle import HerramientaNoDisponible
from src.services.errores_oracle import explicar_error
from src.services.identificadores import IdentificadorInvalido
from src.services.expdp_runner import Conexion
from src.services.recuperacion import (
    RecuperacionFallida,
    nombre_log_recuperacion,
    recuperar_datapump,
    validar_solicitud_datapump,
)
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


# --- recuperar_datapump con éxito (FP-4..FP-7, FA-2a, RN-4, RN-5, RN-8) ---

AHORA = datetime(2024, 6, 1, 9, 45, 7)
CONEXION = Conexion(usuario="SYS", password="clave", servicio="XEPDB1", sysdba=True)


def _entorno_datapump(log="successfully completed", extra=()):
    return EntornoFalso(
        log=log,
        texto="salida de impdp",
        archivos={PurePosixPath("/a"): [_a(f"{BASE}.dmp"), _a(f"{BASE}.log"), *extra]},
    )


def _recuperar(entorno, modo="tablas", objetos=("hr.employees",), existentes="SKIP"):
    return recuperar_datapump(
        _Consulta(), entorno, CONEXION, "respaldo", BASE, modo, list(objetos), existentes, AHORA
    )


@pytest.mark.parametrize("accion", ["SKIP", "APPEND", "TRUNCATE", "REPLACE"])
def test_modo_tablas_lanza_impdp_con_los_parametros_del_respaldo(accion):
    entorno = _entorno_datapump()

    _recuperar(entorno, "tablas", ["hr.employees", "scott.emp"], accion)

    herramienta = entorno.herramientas[0]
    assert herramienta["nombre"] == "impdp"
    assert herramienta["script"].splitlines()[1:] == [
        "DIRECTORY=RESPALDO",
        f"DUMPFILE={BASE}.dmp",
        f"LOGFILE={LOG}",
        "TABLES=HR.EMPLOYEES,SCOTT.EMP",
        f"TABLE_EXISTS_ACTION={accion}",
    ]


@pytest.mark.parametrize("accion", ["SKIP", "APPEND", "TRUNCATE", "REPLACE"])
def test_modo_schemas_usa_schemas_y_nunca_borra_usuarios(accion):
    entorno = _entorno_datapump()

    _recuperar(entorno, "schemas", ["hr", "scott"], accion)

    lineas = entorno.herramientas[0]["script"].splitlines()
    assert "SCHEMAS=HR,SCOTT" in lineas
    assert f"TABLE_EXISTS_ACTION={accion}" in lineas
    assert not any(l.startswith("TABLES=") for l in lineas)
    assert "DROP" not in entorno.herramientas[0]["script"]


def test_con_exito_devuelve_el_log_de_recuperacion_sin_advertencia_si_esta_completo():
    entorno = _entorno_datapump(log="Job successfully completed")

    resultado = _recuperar(entorno)

    assert resultado.log == "Job successfully completed"
    assert resultado.advertencia is None
    assert PurePosixPath("/a") / LOG in entorno.lecturas


def test_si_el_log_no_se_puede_leer_devuelve_la_salida_de_impdp():
    entorno = _entorno_datapump(log=None)

    assert _recuperar(entorno).log == "salida de impdp"


def test_respaldo_no_completo_se_recupera_igual_con_advertencia_del_estado():
    entorno = EntornoFalso(texto="ok", archivos={PurePosixPath("/a"): [_a(f"{BASE}.dmp")]})

    resultado = _recuperar(entorno)

    assert entorno.herramientas[0]["nombre"] == "impdp"
    assert "Sin log" in resultado.advertencia


# --- fallos de recuperar_datapump (FA-4a, FA-4c, FA-4d, FA-5a, FA-5b, RN-11) ---


def test_respaldo_rman_no_se_recupera_con_datapump_y_no_lanza_impdp():
    entorno = EntornoFalso(archivos={PurePosixPath("/a"): [_a(f"{BASE}_USERS_1_1.dbf")]})

    with pytest.raises(RespaldoInvalido, match="Data Pump"):
        _recuperar(entorno)

    assert entorno.herramientas == []


def test_respaldo_sin_dmp_no_lanza_impdp():
    entorno = EntornoFalso(archivos={PurePosixPath("/a"): [_a(f"{BASE}.log")]})

    with pytest.raises(RespaldoInvalido):
        _recuperar(entorno)

    assert entorno.herramientas == []


def test_base_invalida_es_respaldo_invalido():
    entorno = _entorno_datapump()

    with pytest.raises(RespaldoInvalido):
        recuperar_datapump(_Consulta(), entorno, CONEXION, "respaldo", "../x", "tablas", ["hr.e"], "SKIP", AHORA)

    assert entorno.herramientas == []


def test_directorio_inexistente_lanza_directorio_no_encontrado():
    entorno = _entorno_datapump()

    with pytest.raises(DirectorioNoEncontrado):
        recuperar_datapump(_Consulta(), entorno, CONEXION, "otro", BASE, "tablas", ["hr.e"], "SKIP", AHORA)

    assert entorno.herramientas == []


def test_respaldo_inexistente_lanza_respaldo_no_encontrado():
    entorno = _entorno_datapump()

    with pytest.raises(RespaldoNoEncontrado):
        recuperar_datapump(
            _Consulta(), entorno, CONEXION, "respaldo", "x_20240101_000000", "tablas", ["hr.e"], "SKIP", AHORA
        )

    assert entorno.herramientas == []


def test_impdp_con_codigo_distinto_de_cero_lanza_recuperacion_fallida_con_log_y_explicacion():
    entorno = _entorno_datapump(log="ORA-39151: Table exists")
    entorno.codigo = 5

    with pytest.raises(RecuperacionFallida) as error:
        _recuperar(entorno)

    assert error.value.codigo == 5
    assert error.value.log == "ORA-39151: Table exists"
    assert error.value.explicacion == explicar_error("ORA-39151: Table exists")
    assert "impdp" in str(error.value)


def test_recuperacion_fallida_usa_la_salida_si_el_log_no_se_puede_leer():
    entorno = _entorno_datapump(log=None)
    entorno.codigo = 1
    entorno.texto = "ORA-31655: sin objetos"

    with pytest.raises(RecuperacionFallida) as error:
        _recuperar(entorno)

    assert error.value.log == "ORA-31655: sin objetos"


def test_impdp_no_disponible_deja_pasar_herramienta_no_disponible():
    class _SinImpdp(EntornoFalso):
        def ejecutar(self, comando):
            raise HerramientaNoDisponible("impdp")

    entorno = _SinImpdp(archivos={PurePosixPath("/a"): [_a(f"{BASE}.dmp")]})

    with pytest.raises(HerramientaNoDisponible):
        _recuperar(entorno)


def test_un_fallo_no_borra_ni_modifica_los_archivos_del_respaldo():
    entorno = _entorno_datapump()
    entorno.codigo = 1

    with pytest.raises(RecuperacionFallida):
        _recuperar(entorno)

    assert entorno.borrados == []
