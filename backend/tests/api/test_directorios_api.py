import json
from pathlib import PureWindowsPath

import oracledb
import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia, responder
from src.api.dependencias import obtener_conexion, obtener_entorno
from src.services.directorios import DirectorioInvalido, DirectorioNoEncontrado
from src.services.entorno_oracle import OperacionEntornoFallida
from src.services.expdp_runner import Conexion
from tests.services.entorno_falso import EntornoFalso

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}


class EntornoWindows(EntornoFalso):
    tipo_ruta = PureWindowsPath


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


class SentenciaFalsa:
    def __init__(self, error=None):
        self.sqls = []
        self.error = error

    def __call__(self, sql, params=None):
        if self.error:
            raise oracledb.DatabaseError(self.error)
        self.sqls.append(sql)


def usar(filas, entorno=None, sentencia=None, schemas=()):
    def consulta(sql, params=None):
        if "instance_name" in sql.lower():
            return [("XE",)]
        if "all_users" in sql.lower():
            return [(params["schema"],)] if params["schema"] in schemas else []
        return filas

    app.dependency_overrides[obtener_consulta_admin] = lambda: consulta
    app.dependency_overrides[obtener_entorno] = lambda: entorno or EntornoFalso()
    app.dependency_overrides[obtener_sentencia] = lambda: sentencia
    app.dependency_overrides[obtener_conexion] = lambda: Conexion("SYSTEM", "s3creta!", "XEPDB1")


def test_lista_los_directorios_con_nombre_y_ruta_y_los_ejemplos(cliente):
    usar([("BACKUP", "/opt/oracle/respaldos"), ("DATA_PUMP_DIR", "/u01/dpdump")])

    respuesta = cliente.get("/directorios", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "directorios": [
            {"nombre": "BACKUP", "ruta": "/opt/oracle/respaldos"},
            {"nombre": "DATA_PUMP_DIR", "ruta": "/u01/dpdump"},
        ],
        "ejemplos_ruta": ["/opt/oracle/respaldos"],
    }


def test_los_ejemplos_dependen_del_entorno(cliente):
    usar([], EntornoWindows())

    respuesta = cliente.get("/directorios", headers=CABECERAS)

    assert respuesta.json()["ejemplos_ruta"] == ["C:\\respaldos", "\\\\servidor\\recurso"]


def test_sin_directorios_responde_200_con_lista_vacia(cliente):
    usar([])

    respuesta = cliente.get("/directorios", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json()["directorios"] == []


def test_sin_sesion_responde_401(cliente):
    respuesta = cliente.get("/directorios")

    assert respuesta.status_code == 401


def _lanzar(error):
    def accion():
        raise error

    return responder(accion)


def test_responder_mapea_directorio_invalido_a_422():
    respuesta = _lanzar(DirectorioInvalido(["La ruta es obligatoria"]))

    assert respuesta.status_code == 422
    assert json.loads(respuesta.body) == {"errores": ["La ruta es obligatoria"]}


def test_responder_mapea_directorio_no_encontrado_a_404():
    respuesta = _lanzar(DirectorioNoEncontrado("El directorio X no existe"))

    assert respuesta.status_code == 404
    assert json.loads(respuesta.body) == {"detail": "El directorio X no existe"}


def test_responder_mapea_fallo_de_permisos_a_500_con_mensaje_explicacion_y_error():
    respuesta = _lanzar(OperacionEntornoFallida("chown: no such file\nmas detalle"))

    cuerpo = json.loads(respuesta.body)
    assert respuesta.status_code == 500
    assert cuerpo["mensaje"] == "No se pudieron dar permisos a Oracle sobre la carpeta"
    assert "debe existir en el contenedor" in cuerpo["explicacion"]
    assert cuerpo["error"] == "chown: no such file"


def test_crear_directorio_da_permisos_ejecuta_create_sin_grant_y_responde_200(cliente):
    sentencia = SentenciaFalsa()
    entorno = EntornoFalso()
    usar([], entorno, sentencia)

    respuesta = cliente.post(
        "/directorios", json={"nombre": "backup", "ruta": "/opt/oracle/respaldos"}, headers=CABECERAS
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Directorio BACKUP creado"}
    assert [(str(r), sid) for r, sid in entorno.permisos] == [("/opt/oracle/respaldos", "XE")]
    assert sentencia.sqls == ["CREATE DIRECTORY BACKUP AS '/opt/oracle/respaldos'"]


def test_crear_directorio_con_schema_ejecuta_create_y_grant_al_schema_y_responde_200(cliente):
    sentencia = SentenciaFalsa()
    usar([], sentencia=sentencia, schemas=("HR",))

    respuesta = cliente.post(
        "/directorios",
        json={"nombre": "backup", "ruta": "/opt/oracle/respaldos", "schema": "hr"},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Directorio BACKUP creado"}
    assert sentencia.sqls == [
        "CREATE DIRECTORY BACKUP AS '/opt/oracle/respaldos'",
        "GRANT READ, WRITE ON DIRECTORY BACKUP TO HR",
    ]


@pytest.mark.parametrize("schema", ["1mal", "hr"])
def test_crear_directorio_con_schema_invalido_o_inexistente_responde_422_sin_ejecutar_nada(cliente, schema):
    sentencia = SentenciaFalsa()
    entorno = EntornoFalso()
    usar([], entorno, sentencia)

    respuesta = cliente.post(
        "/directorios",
        json={"nombre": "backup", "ruta": "/opt/oracle/respaldos", "schema": schema},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 422
    assert "schema" in respuesta.json()["errores"][0].lower()
    assert sentencia.sqls == []
    assert entorno.permisos == []


def test_crear_directorio_invalido_responde_422_con_los_errores_y_no_ejecuta_nada(cliente):
    sentencia = SentenciaFalsa()
    entorno = EntornoFalso()
    usar([], entorno, sentencia)

    respuesta = cliente.post("/directorios", json={"nombre": "", "ruta": "relativa"}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert len(respuesta.json()["errores"]) == 2
    assert sentencia.sqls == []
    assert entorno.permisos == []


def test_crear_directorio_duplicado_responde_422(cliente):
    sentencia = SentenciaFalsa()
    usar([("BACKUP", "/u01/otro")], sentencia=sentencia)

    respuesta = cliente.post(
        "/directorios", json={"nombre": "backup", "ruta": "/opt/oracle/respaldos"}, headers=CABECERAS
    )

    assert respuesta.status_code == 422
    assert "BACKUP" in respuesta.json()["errores"][0]
    assert sentencia.sqls == []


def test_crear_directorio_con_fallo_de_permisos_responde_500_sin_ejecutar_sentencias(cliente):
    sentencia = SentenciaFalsa()
    usar([], EntornoFalso(fallo_permisos="chown: no such file"), sentencia)

    respuesta = cliente.post(
        "/directorios", json={"nombre": "backup", "ruta": "/opt/oracle/respaldos"}, headers=CABECERAS
    )

    assert respuesta.status_code == 500
    assert respuesta.json()["error"] == "chown: no such file"
    assert sentencia.sqls == []


def test_crear_directorio_si_oracle_rechaza_explica_el_error(cliente):
    usar([], sentencia=SentenciaFalsa(error="ORA-01031: insufficient privileges"))

    respuesta = cliente.post(
        "/directorios", json={"nombre": "backup", "ruta": "/opt/oracle/respaldos"}, headers=CABECERAS
    )

    assert respuesta.status_code == 500
    assert respuesta.json()["error"].startswith("ORA-01031")


def test_editar_directorio_da_permisos_ejecuta_create_or_replace_y_responde_200(cliente):
    sentencia = SentenciaFalsa()
    entorno = EntornoFalso()
    usar([("BACKUP", "/u01/viejo")], entorno, sentencia)

    respuesta = cliente.put("/directorios/backup", json={"ruta": "/opt/oracle/nuevo"}, headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Directorio BACKUP actualizado"}
    assert [(str(r), sid) for r, sid in entorno.permisos] == [("/opt/oracle/nuevo", "XE")]
    assert sentencia.sqls == ["CREATE OR REPLACE DIRECTORY BACKUP AS '/opt/oracle/nuevo'"]


def test_editar_directorio_inexistente_responde_404(cliente):
    sentencia = SentenciaFalsa()
    usar([], sentencia=sentencia)

    respuesta = cliente.put("/directorios/backup", json={"ruta": "/opt/oracle/nuevo"}, headers=CABECERAS)

    assert respuesta.status_code == 404
    assert sentencia.sqls == []


def test_editar_directorio_del_sistema_responde_422(cliente):
    sentencia = SentenciaFalsa()
    usar([("DATA_PUMP_DIR", "/u01/dpdump")], sentencia=sentencia)

    respuesta = cliente.put("/directorios/data_pump_dir", json={"ruta": "/opt/oracle/nuevo"}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert sentencia.sqls == []


def test_editar_directorio_con_ruta_invalida_responde_422(cliente):
    sentencia = SentenciaFalsa()
    usar([("BACKUP", "/u01/viejo")], sentencia=sentencia)

    respuesta = cliente.put("/directorios/backup", json={"ruta": "relativa"}, headers=CABECERAS)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"]
    assert sentencia.sqls == []


def test_editar_directorio_con_fallo_de_permisos_responde_500_sin_ejecutar_sentencias(cliente):
    sentencia = SentenciaFalsa()
    usar([("BACKUP", "/u01/viejo")], EntornoFalso(fallo_permisos="chown: no such file"), sentencia)

    respuesta = cliente.put("/directorios/backup", json={"ruta": "/opt/oracle/nuevo"}, headers=CABECERAS)

    assert respuesta.status_code == 500
    assert respuesta.json()["error"] == "chown: no such file"
    assert sentencia.sqls == []


def test_editar_directorio_si_oracle_rechaza_explica_el_error(cliente):
    usar([("BACKUP", "/u01/viejo")], sentencia=SentenciaFalsa(error="ORA-01031: insufficient privileges"))

    respuesta = cliente.put("/directorios/backup", json={"ruta": "/opt/oracle/nuevo"}, headers=CABECERAS)

    assert respuesta.status_code == 500
    assert respuesta.json()["error"].startswith("ORA-01031")


def test_eliminar_directorio_ejecuta_drop_y_responde_200(cliente):
    sentencia = SentenciaFalsa()
    usar([("BACKUP", "/u01/viejo")], sentencia=sentencia)

    respuesta = cliente.delete("/directorios/backup", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Directorio BACKUP eliminado"}
    assert sentencia.sqls == ["DROP DIRECTORY BACKUP"]


def test_eliminar_directorio_inexistente_responde_404(cliente):
    sentencia = SentenciaFalsa()
    usar([], sentencia=sentencia)

    respuesta = cliente.delete("/directorios/backup", headers=CABECERAS)

    assert respuesta.status_code == 404
    assert sentencia.sqls == []


def test_eliminar_directorio_del_sistema_responde_422(cliente):
    sentencia = SentenciaFalsa()
    usar([("DATA_PUMP_DIR", "/u01/dpdump")], sentencia=sentencia)

    respuesta = cliente.delete("/directorios/data_pump_dir", headers=CABECERAS)

    assert respuesta.status_code == 422
    assert sentencia.sqls == []


def test_eliminar_directorio_si_oracle_rechaza_explica_el_error(cliente):
    usar([("BACKUP", "/u01/viejo")], sentencia=SentenciaFalsa(error="ORA-01031: insufficient privileges"))

    respuesta = cliente.delete("/directorios/backup", headers=CABECERAS)

    assert respuesta.status_code == 500
    assert respuesta.json()["error"].startswith("ORA-01031")
