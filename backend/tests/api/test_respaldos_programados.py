from datetime import datetime

import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_sentencia
from src.api.dependencias import obtener_entorno, obtener_programador
from src.api.respaldos import obtener_consulta
from src.api.sesion import obtener_almacen
from src.services.entorno_oracle import HerramientaNoDisponible, OperacionEntornoFallida
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones
from tests.services.entorno_falso import EntornoFalso

ALMACEN = AlmacenSesiones()
TOKEN_SYSDBA = ALMACEN.crear(
    Conexion(usuario="SYS", password="s3creta!", servicio="XE", sysdba=True)
)
TOKEN_COMUN = ALMACEN.crear(Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1"))
SYSDBA = {"Authorization": f"Bearer {TOKEN_SYSDBA}"}
COMUN = {"Authorization": f"Bearer {TOKEN_COMUN}"}
RUTA = "/opt/oracle/Respaldos"
HOME = "/opt/oracle/product/21c/dbhome_1"
RMAN = f"{RUTA}/scripts_programados/diario.rman"
SH = f"{RUTA}/scripts_programados/diario.sh"
SOLICITUD = {
    "nombre": "diario",
    "directorio": "RESPALDO",
    "politica": "FULL",
    "frecuencia": "DIARIO",
    "hora": "02:30",
}
CREADO = datetime(2026, 5, 1, 2, 30, 15)
EJECUTADO = datetime(2026, 5, 2, 2, 30, 40)

ENDPOINTS = [
    ("post", "/respaldos/programados", SOLICITUD),
    ("get", "/respaldos/programados", None),
]


def fila(id=1, nombre="diario", ultima=EJECUTADO, resultado="Completo"):
    return (
        id, nombre, "FULL", "DIARIO", "02:30", None, None, "RESPALDO", SH, RMAN,
        "contenedor", f"OracleAdmin_{id}", CREADO, ultima, resultado,
    )


class ConsultaFalsa:
    def __init__(self, modo="ARCHIVELOG", filas=(), error=None, directorios=(("RESPALDO", RUTA),)):
        self.modo = modo
        self.filas = list(filas)
        self.error = error
        self.directorios = list(directorios)

    def __call__(self, sql, params=None):
        sql = sql.lower()
        if "instance_name" in sql:
            return [("XE",)]
        if "v$database" in sql:
            return [(self.modo,)]
        if "where nombre" in sql:
            return [(7,)]
        if "respaldos_programados" in sql:
            if self.error:
                raise self.error
            return self.filas
        return self.directorios


class SentenciaFalsa:
    def __init__(self, error_en=None):
        self.error_en = error_en
        self.llamadas = []

    def __call__(self, sql, params=None):
        if self.error_en and sql.startswith(self.error_en[0]):
            raise self.error_en[1]
        self.llamadas.append((sql, params))


class ProgramadorFalso:
    def __init__(self, error=None):
        self.error = error
        self.instalaciones = []

    def instalar(self, id_programacion, prog, ruta_script):
        if self.error:
            raise self.error
        self.instalaciones.append((id_programacion, prog, ruta_script))


@pytest.fixture
def cliente():
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(consulta=None, sentencia=None, entorno=None, programador=None):
    consulta = consulta or ConsultaFalsa()
    sentencia = sentencia or SentenciaFalsa()
    entorno = entorno or EntornoFalso(variables_entorno={"ORACLE_HOME": HOME})
    programador = programador or ProgramadorFalso()
    app.dependency_overrides[obtener_consulta] = lambda: consulta
    app.dependency_overrides[obtener_sentencia] = lambda: sentencia
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    app.dependency_overrides[obtener_programador] = lambda: programador
    return sentencia, entorno, programador


def pedir(cliente, metodo, ruta, cuerpo, cabeceras):
    if cuerpo is None:
        return getattr(cliente, metodo)(ruta, headers=cabeceras)
    return getattr(cliente, metodo)(ruta, json=cuerpo, headers=cabeceras)


def sin_efectos(sentencia, entorno, programador):
    assert sentencia.llamadas == []
    assert entorno.herramientas == []
    assert entorno.escrituras == []
    assert programador.instalaciones == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", ENDPOINTS)
def test_sin_token_responde_401(cliente, metodo, ruta, cuerpo):
    efectos = usar()

    assert pedir(cliente, metodo, ruta, cuerpo, {}).status_code == 401
    sin_efectos(*efectos)


@pytest.mark.parametrize("metodo, ruta, cuerpo", ENDPOINTS)
def test_una_sesion_sin_sysdba_responde_403_sin_tocar_nada(cliente, metodo, ruta, cuerpo):
    efectos = usar()

    respuesta = pedir(cliente, metodo, ruta, cuerpo, COMUN)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Se requiere sesión SYSDBA"
    sin_efectos(*efectos)


def test_programa_el_respaldo_y_devuelve_id_y_rutas(cliente):
    sentencia, entorno, programador = usar()

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "mensaje": "Respaldo programado", "id": 7, "ruta_script": SH, "ruta_rman": RMAN,
    }
    assert [str(e[0]) for e in entorno.escrituras] == [RMAN, SH]
    assert [h["nombre"] for h in entorno.herramientas] == ["rman"]
    assert entorno.herramientas[0]["variables"] == {"ORACLE_SID": "XE"}
    (id_tarea, prog, ruta), = programador.instalaciones
    assert (id_tarea, ruta) == (7, SH)
    assert (prog.nombre, prog.politica, prog.frecuencia, prog.hora, prog.dia, prog.intervalo_horas) == (
        "diario", "FULL", "DIARIO", "02:30", None, 2,
    )
    insert = next(p for sql, p in sentencia.llamadas if sql.startswith("INSERT"))
    assert insert["entorno"] == "contenedor"
    assert "s3creta!" not in respuesta.text


def test_los_datos_invalidos_responden_422_con_los_errores_sin_llamar_al_entorno(cliente):
    efectos = usar()

    respuesta = cliente.post("/respaldos/programados", json={}, headers=SYSDBA)

    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert "Debes ingresar un nombre para la programación" in errores
    assert "Debes elegir un directorio" in errores
    assert all("dumpfile" not in e for e in errores)
    sin_efectos(*efectos)


def test_un_dia_de_tipo_raro_sale_como_error_de_validacion_y_no_de_pydantic(cliente):
    efectos = usar()
    cuerpo = {**SOLICITUD, "frecuencia": "SEMANAL", "dia": "x"}

    respuesta = cliente.post("/respaldos/programados", json=cuerpo, headers=SYSDBA)

    assert respuesta.status_code == 422
    assert list(respuesta.json()) == ["errores"]
    assert any("día de la semana" in e for e in respuesta.json()["errores"])
    sin_efectos(*efectos)


def test_sin_archivelog_responde_409_con_explicacion_y_no_hace_nada(cliente):
    efectos = usar(consulta=ConsultaFalsa("NOARCHIVELOG"))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert "ARCHIVELOG" in cuerpo["mensaje"] and "ARCHIVELOG" in cuerpo["explicacion"]
    sin_efectos(*efectos)


def test_un_nombre_repetido_responde_409_con_mensaje(cliente):
    efectos = usar(consulta=ConsultaFalsa(filas=[fila()]))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": "Ya existe una programación con ese nombre"}
    sin_efectos(*efectos)


def comprobar_500(respuesta, log, explicacion):
    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["mensaje"] == "No se pudo programar el respaldo"
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert cuerpo["log"] == log
    assert explicacion in cuerpo["explicacion"]
    assert "s3creta!" not in respuesta.text


def test_si_falla_la_tabla_responde_500_con_explicacion_y_log(cliente):
    error = oracledb.DatabaseError("ORA-01031: privilegios insuficientes")
    _, entorno, _ = usar(sentencia=SentenciaFalsa(("CREATE", error)))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    comprobar_500(respuesta, "ORA-01031: privilegios insuficientes", "privilegios")
    assert entorno.escrituras == []


def test_si_falla_la_politica_responde_500_con_la_explicacion_y_el_log_de_rman(cliente):
    _, entorno, programador = usar(entorno=EntornoFalso(
        codigo=1, texto="RMAN-06059: falta un archivelog", variables_entorno={"ORACLE_HOME": HOME},
    ))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    comprobar_500(respuesta, "RMAN-06059: falta un archivelog", "Faltan archivelogs")
    assert entorno.escrituras == [] and programador.instalaciones == []


def test_si_falla_la_escritura_responde_500_y_no_instala_la_tarea(cliente):
    _, _, programador = usar(entorno=EntornoFalso(
        fallo_escritura="sin espacio en disco", variables_entorno={"ORACLE_HOME": HOME},
    ))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    comprobar_500(respuesta, "sin espacio en disco", "")
    assert programador.instalaciones == []


def test_si_falla_el_programador_responde_500_y_deshace_los_scripts(cliente):
    _, entorno, _ = usar(programador=ProgramadorFalso(OperacionEntornoFallida("crontab: acceso denegado")))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    comprobar_500(respuesta, "crontab: acceso denegado", "")
    assert sorted(str(r) for r in entorno.borrados) == [RMAN, SH]


def test_herramienta_no_disponible_responde_500_con_el_mensaje(cliente):
    error = HerramientaNoDisponible("crontab")
    usar(programador=ProgramadorFalso(error))

    respuesta = cliente.post("/respaldos/programados", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 500
    assert respuesta.json() == {"mensaje": str(error)}


def test_lista_las_programaciones_con_fechas_iso(cliente):
    usar(consulta=ConsultaFalsa(filas=[fila(1), fila(2, "semanal", None, None)]))

    respuesta = cliente.get("/respaldos/programados", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"programaciones": [
        {
            "id": 1, "nombre": "diario", "politica": "FULL", "frecuencia": "DIARIO", "hora": "02:30",
            "dia": None, "intervalo_horas": None, "directorio": "RESPALDO", "ruta_script": SH,
            "ruta_rman": RMAN, "entorno": "contenedor", "tarea": "OracleAdmin_1",
            "creado": "2026-05-01T02:30:15", "ultima_ejecucion": "2026-05-02T02:30:40",
            "ultimo_resultado": "Completo",
        },
        {
            "id": 2, "nombre": "semanal", "politica": "FULL", "frecuencia": "DIARIO", "hora": "02:30",
            "dia": None, "intervalo_horas": None, "directorio": "RESPALDO", "ruta_script": SH,
            "ruta_rman": RMAN, "entorno": "contenedor", "tarea": "OracleAdmin_2",
            "creado": "2026-05-01T02:30:15", "ultima_ejecucion": None, "ultimo_resultado": None,
        },
    ]}


def test_con_la_tabla_inexistente_la_lista_esta_vacia(cliente):
    usar(consulta=ConsultaFalsa(error=oracledb.DatabaseError("ORA-00942: la tabla no existe")))

    respuesta = cliente.get("/respaldos/programados", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"programaciones": []}
