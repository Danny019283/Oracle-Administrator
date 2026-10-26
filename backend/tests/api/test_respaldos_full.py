import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.respaldos import obtener_consulta, obtener_ejecutor
from src.api.sesion import obtener_almacen
from src.services.expdp_runner import Conexion, Salida
from src.services.sesiones import AlmacenSesiones

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
    def __init__(self, modo="ARCHIVELOG", directorios=(("RESPALDO", RUTA),)):
        self.modo = modo
        self.directorios = list(directorios)

    def __call__(self, sql, params=None):
        if "v$database" in sql.lower():
            return [(self.modo,)]
        return self.directorios


class EjecutorFalso:
    """`salidas` da la Salida de cada ejecución de RMAN, en orden (backup, limpieza)."""

    def __init__(self, salidas=None, sqlplus=Salida(0, "base abierta")):
        self.salidas = salidas or [Salida(0, "log del backup"), Salida(0, "log de la limpieza")]
        self.sqlplus = sqlplus
        self.llamadas = []
        self.ejecuciones_rman = 0

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "rman" in args:
            salida = self.salidas[self.ejecuciones_rman]
            self.ejecuciones_rman += 1
            return salida
        if "sqlplus" in args:
            return self.sqlplus
        return Salida(codigo=0, texto="")


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ORACLE_CONTAINER", "oracle-test")
    app.dependency_overrides[obtener_almacen] = lambda: ALMACEN
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(consulta=None, ejecutor=None):
    consulta = consulta or ConsultaFalsa()
    ejecutor = ejecutor or EjecutorFalso()
    app.dependency_overrides[obtener_consulta] = lambda: consulta
    app.dependency_overrides[obtener_ejecutor] = lambda: ejecutor
    return ejecutor


def pedir(cliente, metodo, ruta, cuerpo, cabeceras):
    return getattr(cliente, metodo)(ruta, json=cuerpo, headers=cabeceras) if cuerpo is not None else getattr(cliente, metodo)(ruta, headers=cabeceras)


@pytest.mark.parametrize("metodo, ruta, cuerpo", ENDPOINTS)
def test_sin_token_responde_401(cliente, metodo, ruta, cuerpo):
    ejecutor = usar()

    respuesta = pedir(cliente, metodo, ruta, cuerpo, {})

    assert respuesta.status_code == 401
    assert ejecutor.llamadas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", ENDPOINTS)
def test_una_sesion_sin_sysdba_responde_403_y_no_ejecuta_nada(cliente, metodo, ruta, cuerpo):
    ejecutor = usar()

    respuesta = pedir(cliente, metodo, ruta, cuerpo, COMUN)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Se requiere sesión SYSDBA"
    assert ejecutor.llamadas == []


@pytest.mark.parametrize("modo, esperado", [("ARCHIVELOG", True), ("NOARCHIVELOG", False)])
def test_el_estado_informa_si_la_base_esta_en_archivelog(cliente, modo, esperado):
    usar(consulta=ConsultaFalsa(modo))

    respuesta = cliente.get("/respaldos/full/estado", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"archivelog": esperado}


def test_respalda_y_devuelve_el_log_de_rman_sin_advertencia(cliente):
    ejecutor = usar()

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"log": "log del backup", "advertencia": None}
    assert ejecutor.ejecuciones_rman == 2
    assert "s3creta!" not in respuesta.text
    rman = next(args for args, _ in ejecutor.llamadas if "rman" in args)
    assert rman[:3] == ["docker", "exec", "oracle-test"]


def test_si_la_limpieza_falla_responde_200_con_la_advertencia_y_su_log(cliente):
    usar(
        ejecutor=EjecutorFalso(
            [Salida(0, "log del backup"), Salida(1, "RMAN-06059: falta un archivelog")]
        )
    )

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["log"] == "log del backup"
    assert cuerpo["advertencia"]["log"] == "RMAN-06059: falta un archivelog"
    assert "Faltan archivelogs" in cuerpo["advertencia"]["explicacion"]


def test_si_el_backup_falla_responde_500_con_mensaje_explicacion_y_log_sin_limpieza(cliente):
    ejecutor = usar(
        ejecutor=EjecutorFalso([Salida(1, "RMAN-03002: fallo\nRMAN-06059: falta un archivelog")])
    )

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "explicacion", "log"}
    assert "rman terminó con código 1" in cuerpo["mensaje"]
    assert "Faltan archivelogs" in cuerpo["explicacion"]
    assert "RMAN-06059" in cuerpo["log"]
    assert ejecutor.ejecuciones_rman == 1


def test_sin_archivelog_responde_409_con_explicacion_y_no_ejecuta_rman(cliente):
    ejecutor = usar(consulta=ConsultaFalsa("NOARCHIVELOG"))

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert "ARCHIVELOG" in cuerpo["mensaje"]
    assert "ARCHIVELOG" in cuerpo["explicacion"]
    assert ejecutor.llamadas == []


def test_solicitud_invalida_responde_422_con_cada_dato_faltante_y_no_ejecuta_rman(cliente):
    ejecutor = usar()

    respuesta = cliente.post("/respaldos/full", json={}, headers=SYSDBA)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        "Debes elegir un directorio",
        "Debes ingresar un nombre de dumpfile",
    ]
    assert ejecutor.llamadas == []


def test_sin_directorios_la_solicitud_se_rechaza_con_422(cliente):
    ejecutor = usar(consulta=ConsultaFalsa(directorios=[]))

    respuesta = cliente.post("/respaldos/full", json=SOLICITUD, headers=SYSDBA)

    assert respuesta.status_code == 422
    assert "El directorio RESPALDO no está disponible" in respuesta.json()["errores"]
    assert ejecutor.llamadas == []


def test_activa_archivelog_y_pide_iniciar_sesion_de_nuevo(cliente):
    ejecutor = usar()

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 200
    assert respuesta.json()["mensaje"] == "ARCHIVELOG activado. Inicia sesión de nuevo"
    sqlplus = next(args for args, _ in ejecutor.llamadas if "sqlplus" in args)
    assert sqlplus[:3] == ["docker", "exec", "oracle-test"]
    assert "s3creta!" not in respuesta.text


def test_si_activar_archivelog_falla_responde_500_con_mensaje_explicacion_y_log(cliente):
    usar(ejecutor=EjecutorFalso(sqlplus=Salida(1, "ORA-19809: límite de la FRA superado")))

    respuesta = cliente.post("/respaldos/full/archivelog", headers=SYSDBA)

    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "mensaje": "No se pudo activar ARCHIVELOG",
        "explicacion": "Se superó el límite de la zona de recuperación (FRA)",
        "log": "ORA-19809: límite de la FRA superado",
    }
