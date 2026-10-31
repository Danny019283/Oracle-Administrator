import time
from datetime import datetime

import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_sentencia
from src.api.dependencias import obtener_entorno, obtener_programador
from src.api.respaldos import obtener_consulta
from src.api.sesion import obtener_almacen
from src.services.entorno_oracle import ArchivoEntorno, HerramientaNoDisponible, OperacionEntornoFallida
from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones
from tests.services.entorno_falso import EntornoFalso

ALMACEN = AlmacenSesiones()
SYSDBA = {"Authorization": "Bearer " + ALMACEN.crear(
    Conexion(usuario="SYS", password="s3creta!", servicio="XE", sysdba=True))}
COMUN = {"Authorization": "Bearer " + ALMACEN.crear(Conexion(usuario="HR", password="s3creta!", servicio="XEPDB1"))}
RUTA = "/opt/oracle/Respaldos"
HOME = "/opt/oracle/product/21c/dbhome_1"
RMAN = f"{RUTA}/scripts_programados/diario.rman"
SH = f"{RUTA}/scripts_programados/diario.sh"
CREADO = datetime(2026, 5, 1, 2, 30, 15)
SCRIPT_EN_DISCO = ArchivoEntorno("diario.sh", 1, 1.0)

ENDPOINTS = [
    ("post", "/respaldos/programados/1/ejecutar"),
    ("delete", "/respaldos/programados/1"),
    ("post", "/respaldos/programados/reinstalar"),
]


def fila(id=1, nombre="diario"):
    return (
        id, nombre, "FULL", "DIARIO", "02:30", None, None, "RESPALDO", SH, RMAN,
        "contenedor", f"OracleAdmin_{id}", CREADO, None, None,
    )


class ConsultaFalsa:
    def __init__(self, filas=()):
        self.filas = list(filas)

    def __call__(self, sql, params=None):
        if "instance_name" in sql.lower():
            return [("XE",)]
        return self.filas


class SentenciaFalsa:
    def __init__(self):
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))


class ProgramadorFalso:
    def __init__(self, error_eliminar=None, error_instalar_en=None):
        self.error_eliminar = error_eliminar
        self.error_instalar_en = error_instalar_en or {}
        self.eliminadas = []
        self.instalaciones = []

    def instalar(self, id_programacion, prog, ruta_script):
        if id_programacion in self.error_instalar_en:
            raise self.error_instalar_en[id_programacion]
        self.instalaciones.append(id_programacion)

    def eliminar(self, id_programacion):
        if self.error_eliminar:
            raise self.error_eliminar
        self.eliminadas.append(id_programacion)


@pytest.fixture
def cliente():
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(filas=(), entorno=None, programador=None):
    sentencia = SentenciaFalsa()
    entorno = entorno or EntornoFalso(archivos=[SCRIPT_EN_DISCO], variables_entorno={"ORACLE_HOME": HOME})
    programador = programador or ProgramadorFalso()
    app.dependency_overrides[obtener_consulta] = lambda: ConsultaFalsa(filas)
    app.dependency_overrides[obtener_sentencia] = lambda: sentencia
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    app.dependency_overrides[obtener_programador] = lambda: programador
    return sentencia, entorno, programador


def sin_efectos(sentencia, entorno, programador):
    assert sentencia.llamadas == []
    assert entorno.ejecuciones == [] and entorno.escrituras == [] and entorno.borrados == []
    assert programador.eliminadas == [] and programador.instalaciones == []


@pytest.mark.parametrize("metodo, ruta", ENDPOINTS)
def test_sin_token_responde_401(cliente, metodo, ruta):
    efectos = usar([fila()])

    assert getattr(cliente, metodo)(ruta).status_code == 401
    sin_efectos(*efectos)


@pytest.mark.parametrize("metodo, ruta", ENDPOINTS)
def test_una_sesion_sin_sysdba_responde_403_sin_tocar_nada(cliente, metodo, ruta):
    efectos = usar([fila()])

    respuesta = getattr(cliente, metodo)(ruta, headers=COMUN)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Se requiere sesión SYSDBA"
    sin_efectos(*efectos)


# --- ejecutar ---


def test_ejecutar_responde_200_con_el_resultado_y_el_log_de_esta_ejecucion(cliente):
    log = ArchivoEntorno("diario_20260502_023040.log", 1, time.time())
    sentencia, entorno, _ = usar([fila()], EntornoFalso(archivos=[SCRIPT_EN_DISCO, log], log="LOG RMAN"))

    respuesta = cliente.post("/respaldos/programados/1/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Respaldo ejecutado", "resultado": "Completo", "log": "LOG RMAN"}
    assert [str(r) for r in entorno.ejecuciones] == [SH]
    assert sentencia.llamadas[0][1] == {"id": 1, "resultado": "Completo"}
    assert "s3creta!" not in respuesta.text


def test_ejecutar_acota_el_log_a_la_ejecucion_actual_con_el_reloj(cliente):
    viejo = ArchivoEntorno("diario_20200101_000000.log", 1, 1.0)
    usar([fila()], EntornoFalso(archivos=[SCRIPT_EN_DISCO, viejo], log="LOG VIEJO", texto="salida actual"))

    respuesta = cliente.post("/respaldos/programados/1/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json()["log"] == "salida actual"


def test_ejecutar_una_programacion_inexistente_responde_404_con_detail(cliente):
    efectos = usar([])

    respuesta = cliente.post("/respaldos/programados/9/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No existe la programación indicada"}
    sin_efectos(*efectos)


def test_ejecutar_con_el_script_ausente_responde_409_sin_ejecutar_y_sugiere_reinstalar(cliente):
    efectos = usar([fila()], EntornoFalso(archivos=[]))

    respuesta = cliente.post("/respaldos/programados/1/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert "Reinstalar tareas" in cuerpo["mensaje"] and cuerpo["detail"] == cuerpo["mensaje"]
    sin_efectos(*efectos)


def test_ejecutar_con_rman_fallido_responde_500_con_explicacion_y_log_y_marca_con_errores(cliente):
    log = ArchivoEntorno("diario_20260502_023040.log", 1, time.time())
    sentencia, _, _ = usar([fila()], EntornoFalso(
        archivos=[SCRIPT_EN_DISCO, log], codigo=1, log="RMAN-06059: falta un archivelog"))

    respuesta = cliente.post("/respaldos/programados/1/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["mensaje"] == "No se pudo ejecutar el respaldo programado"
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert cuerpo["log"] == "RMAN-06059: falta un archivelog"
    assert "Faltan archivelogs" in cuerpo["explicacion"]
    assert sentencia.llamadas[0][1] == {"id": 1, "resultado": "Con errores"}
    assert "s3creta!" not in respuesta.text


def test_ejecutar_con_la_herramienta_ausente_responde_500_con_el_mensaje(cliente):
    usar([fila()], EntornoFalso(archivos=[SCRIPT_EN_DISCO], herramienta_ausente="sh"))

    respuesta = cliente.post("/respaldos/programados/1/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert respuesta.json() == {"mensaje": str(HerramientaNoDisponible("sh"))}


def test_ejecutar_con_fallo_de_oracle_responde_500_con_explicacion_y_log(cliente):
    usar([fila()], EntornoFalso(fallo_listado="sin acceso al disco"))

    respuesta = cliente.post("/respaldos/programados/1/ejecutar", headers=SYSDBA)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["mensaje"] == "No se pudo ejecutar el respaldo programado"
    assert cuerpo["log"] == "sin acceso al disco"
    assert "explicacion" in cuerpo


# --- eliminar ---


def test_eliminar_responde_200_con_el_nombre_y_borra_tarea_scripts_y_fila(cliente):
    sentencia, entorno, programador = usar([fila()])

    respuesta = cliente.delete("/respaldos/programados/1", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Programación diario eliminada"}
    assert programador.eliminadas == [1]
    assert [str(r) for r in entorno.borrados] == [SH, RMAN]
    assert sentencia.llamadas[0][0].startswith("DELETE") and sentencia.llamadas[0][1] == {"id": 1}


def test_eliminar_una_programacion_inexistente_responde_404_con_detail(cliente):
    efectos = usar([])

    respuesta = cliente.delete("/respaldos/programados/9", headers=SYSDBA)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No existe la programación indicada"}
    sin_efectos(*efectos)


def test_eliminar_con_fallo_del_programador_responde_500_sin_borrar_nada(cliente):
    sentencia, entorno, _ = usar([fila()], programador=ProgramadorFalso(
        error_eliminar=OperacionEntornoFallida("crontab: acceso denegado")))

    respuesta = cliente.delete("/respaldos/programados/1", headers=SYSDBA)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["mensaje"] == "No se pudo eliminar la programación"
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert cuerpo["log"] == "crontab: acceso denegado"
    assert entorno.borrados == [] and sentencia.llamadas == []
    assert "s3creta!" not in respuesta.text


def test_eliminar_con_herramienta_ausente_responde_500_con_el_mismo_formato(cliente):
    usar([fila()], programador=ProgramadorFalso(error_eliminar=HerramientaNoDisponible("crontab")))

    respuesta = cliente.delete("/respaldos/programados/1", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert respuesta.json()["mensaje"] == "No se pudo eliminar la programación"


def test_eliminar_con_fallo_al_borrar_scripts_responde_500_y_conserva_la_fila(cliente):
    sentencia, _, _ = usar([fila()], EntornoFalso(fallo_borrado="permiso denegado"))

    respuesta = cliente.delete("/respaldos/programados/1", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert respuesta.json()["log"] == "permiso denegado"
    assert sentencia.llamadas == []


def test_eliminar_con_error_de_oracle_responde_500(cliente):
    class Falla(SentenciaFalsa):
        def __call__(self, sql, params=None):
            raise oracledb.DatabaseError("ORA-01031: privilegios insuficientes")

    usar([fila()])
    app.dependency_overrides[obtener_sentencia] = lambda: Falla()

    respuesta = cliente.delete("/respaldos/programados/1", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert "privilegios" in respuesta.json()["explicacion"]


# --- reinstalar ---


def test_reinstalar_responde_200_con_el_conteo(cliente):
    _, _, programador = usar([fila(1), fila(2, "semanal")], EntornoFalso(
        archivos=[], variables_entorno={"ORACLE_HOME": HOME}))

    respuesta = cliente.post("/respaldos/programados/reinstalar", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "2 programaciones reinstaladas", "reinstaladas": 2, "fallidas": []}
    assert programador.instalaciones == [1, 2]
    assert "s3creta!" not in respuesta.text


def test_reinstalar_una_sola_usa_el_singular(cliente):
    usar([fila()])

    respuesta = cliente.post("/respaldos/programados/reinstalar", headers=SYSDBA)

    assert respuesta.json()["mensaje"] == "1 programación reinstalada"


def test_reinstalar_con_fallidas_responde_200_e_informa_cuales(cliente):
    _, _, programador = usar(
        [fila(1), fila(2, "semanal")],
        programador=ProgramadorFalso(error_instalar_en={2: OperacionEntornoFallida("crontab: acceso denegado")}),
    )

    respuesta = cliente.post("/respaldos/programados/reinstalar", headers=SYSDBA)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["reinstaladas"] == 1
    assert cuerpo["fallidas"] == [{"nombre": "semanal", "mensaje": "crontab: acceso denegado"}]
    assert cuerpo["mensaje"].startswith("1 programación reinstalada") and "1 falló" in cuerpo["mensaje"]
    assert programador.instalaciones == [1]


def test_reinstalar_con_la_tabla_vacia_responde_200_con_cero(cliente):
    usar([])

    respuesta = cliente.post("/respaldos/programados/reinstalar", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "0 programaciones reinstaladas", "reinstaladas": 0, "fallidas": []}
