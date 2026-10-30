import re

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.dependencias import obtener_entorno
from src.api.respaldos import obtener_consulta
from src.api.sesion import obtener_almacen
from src.services.entorno_oracle import Salida
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
SOLICITUD = {"directorio": "RESPALDO", "nombre": "semanal"}

ENDPOINTS = [
    ("get", "/respaldos/full/estado", None),
    ("post", "/respaldos/full", SOLICITUD),
    ("post", "/respaldos/full/archivelog", None),
]


class ConsultaFalsa:
    def __init__(self, modo="ARCHIVELOG", directorios=(("RESPALDO", RUTA),), sid="XE"):
        self.modo = modo
        self.directorios = list(directorios)
        self.sid = sid

    def __call__(self, sql, params=None):
        if "instance_name" in sql.lower():
            return [(self.sid,)]
        if "v$database" in sql.lower():
            return [(self.modo,)]
        return self.directorios


def entorno_rman(*salidas):
    """Entorno falso con la Salida de cada ejecución de RMAN, en orden (backup, limpieza)."""
    return EntornoFalso(salidas=salidas or [Salida(0, "log del backup"), Salida(0, "log de la limpieza")])


@pytest.fixture
def cliente():
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(consulta=None, entorno=None):
    consulta = consulta or ConsultaFalsa()
    entorno = entorno or entorno_rman()
    app.dependency_overrides[obtener_consulta] = lambda: consulta
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    return entorno


def pedir(cliente, metodo, ruta, cuerpo, cabeceras):
    return getattr(cliente, metodo)(ruta, json=cuerpo, headers=cabeceras) if cuerpo is not None else getattr(cliente, metodo)(ruta, headers=cabeceras)


@pytest.mark.parametrize("metodo, ruta, cuerpo", ENDPOINTS)
def test_sin_token_responde_401(cliente, metodo, ruta, cuerpo):
    entorno = usar()

    respuesta = pedir(cliente, metodo, ruta, cuerpo, {})

    assert respuesta.status_code == 401
    assert entorno.herramientas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", ENDPOINTS)
def test_una_sesion_sin_sysdba_responde_403_y_no_ejecuta_nada(cliente, metodo, ruta, cuerpo):
    entorno = usar()

    respuesta = pedir(cliente, metodo, ruta, cuerpo, COMUN)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Se requiere sesión SYSDBA"
    assert entorno.herramientas == []
    assert entorno.carpetas == []


@pytest.mark.parametrize("modo, esperado", [("ARCHIVELOG", True), ("NOARCHIVELOG", False)])
def test_el_estado_informa_si_la_base_esta_en_archivelog(cliente, modo, esperado):
    usar(consulta=ConsultaFalsa(modo))

    respuesta = cliente.get("/respaldos/full/estado", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"archivelog": esperado}


def test_respalda_y_devuelve_el_log_de_rman_sin_advertencia(cliente):
    entorno = usar()

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"log": "log del backup", "advertencia": None}
    assert [h["nombre"] for h in entorno.herramientas] == ["rman", "rman"]
    assert "s3creta!" not in respuesta.text


def test_el_backup_genera_piezas_dbf_y_un_log_con_la_hora_actual_en_la_base(cliente):
    entorno = usar()

    cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    script = entorno.herramientas[0]["script"]
    base = r"semanal_\d{8}_\d{6}"
    assert re.search(rf"FORMAT '{RUTA}/{base}_%d_%s_%p\.dbf'", script)
    assert re.search(rf"^SPOOL LOG TO '{RUTA}/{base}\.log';", script)
    assert script.rstrip().endswith("SPOOL LOG OFF;")


def test_rman_usa_el_sid_real_de_la_instancia_aunque_la_sesion_sea_de_un_servicio_de_pdb(cliente):
    # la sesión del test usa el servicio XE; el SID sale de la consulta, no del servicio
    entorno = usar(consulta=ConsultaFalsa(sid="ORCLCDB"))

    cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert [h["variables"] for h in entorno.herramientas] == [{"ORACLE_SID": "ORCLCDB"}] * 2


def test_si_la_limpieza_falla_responde_200_con_la_advertencia_y_su_log(cliente):
    usar(
        entorno=entorno_rman(
            Salida(0, "log del backup"), Salida(1, "RMAN-06059: falta un archivelog")
        )
    )

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["log"] == "log del backup"
    assert cuerpo["advertencia"]["log"] == "RMAN-06059: falta un archivelog"
    assert "Faltan archivelogs" in cuerpo["advertencia"]["explicacion"]


def test_si_el_backup_falla_responde_500_con_mensaje_explicacion_y_log_sin_limpieza(cliente):
    entorno = usar(
        entorno=entorno_rman(Salida(1, "RMAN-03002: fallo\nRMAN-06059: falta un archivelog"))
    )

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert "rman terminó con código 1" in cuerpo["mensaje"]
    assert "Faltan archivelogs" in cuerpo["explicacion"]
    assert "RMAN-06059" in cuerpo["log"]
    assert len(entorno.herramientas) == 1


def test_sin_archivelog_responde_409_con_explicacion_y_no_ejecuta_rman(cliente):
    entorno = usar(consulta=ConsultaFalsa("NOARCHIVELOG"))

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert "ARCHIVELOG" in cuerpo["mensaje"]
    assert "ARCHIVELOG" in cuerpo["explicacion"]
    assert entorno.herramientas == []


def test_solicitud_invalida_responde_422_con_cada_dato_faltante_y_no_ejecuta_rman(cliente):
    entorno = usar()

    respuesta = cliente.post("/respaldos/full", json={}, headers=SYSDBA)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        "Debes elegir un directorio",
        "Debes ingresar un nombre de dumpfile",
    ]
    assert entorno.herramientas == []


def test_sin_directorios_la_solicitud_se_rechaza_con_422(cliente):
    entorno = usar(consulta=ConsultaFalsa(directorios=[]))

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 422
    assert "El directorio RESPALDO no está disponible" in respuesta.json()["errores"]
    assert entorno.herramientas == []


def test_activa_archivelog_y_pide_iniciar_sesion_de_nuevo(cliente):
    entorno = usar(entorno=EntornoFalso(texto="base abierta"))

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json()["mensaje"] == "ARCHIVELOG activado. Inicia sesión de nuevo"
    assert [h["nombre"] for h in entorno.herramientas] == ["sqlplus"]
    assert "s3creta!" not in respuesta.text


def test_activar_archivelog_usa_el_sid_real_de_la_instancia(cliente):
    entorno = usar(consulta=ConsultaFalsa(sid="ORCLCDB"), entorno=EntornoFalso())

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert entorno.herramientas[0]["variables"] == {"ORACLE_SID": "ORCLCDB"}


def test_si_activar_archivelog_falla_responde_500_con_mensaje_explicacion_y_log(cliente):
    usar(entorno=EntornoFalso(codigo=1, texto="ORA-19809: límite de la FRA superado"))

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "mensaje": "No se pudo activar ARCHIVELOG",
        "explicacion": "Se superó el límite de la zona de recuperación (FRA)",
        "log": "ORA-19809: límite de la FRA superado",
    }
