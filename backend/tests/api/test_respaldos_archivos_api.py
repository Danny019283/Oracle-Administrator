from pathlib import PurePosixPath

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.admin_comun import obtener_consulta_admin, obtener_sentencia
from src.api.dependencias import obtener_conexion, obtener_entorno
from src.services.entorno_oracle import ArchivoEntorno
from src.services.expdp_runner import Conexion
from tests.services.entorno_falso import EntornoFalso

CABECERAS = {
    "X-Oracle-User": "SYSTEM",
    "X-Oracle-Password": "s3creta!",
    "X-Oracle-Service": "XEPDB1",
}
LOG_DP = "Job successfully completed"


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def usar(directorios, entorno, roles=(("DBA",),), sysdba=False):
    def consulta(sql, params=None):
        if "session_roles" in sql.lower():
            return list(roles)
        return directorios

    app.dependency_overrides[obtener_consulta_admin] = lambda: consulta
    app.dependency_overrides[obtener_entorno] = lambda: entorno
    app.dependency_overrides[obtener_conexion] = lambda: Conexion("SYSTEM", "s3creta!", "XEPDB1", sysdba=sysdba)


def test_lista_los_respaldos_con_directorio_logico_ruta_fisica_y_orden(cliente):
    entorno = EntornoFalso(
        log=LOG_DP,
        archivos={
            PurePosixPath("/respaldos"): [
                ArchivoEntorno("hr_20240101_100000.dmp", 100, 0),
                ArchivoEntorno("hr_20240101_100000.log", 5, 0),
                ArchivoEntorno("hr_20240301_100000.dmp", 200, 0),
                ArchivoEntorno("hr_20240301_100000.log", 7, 0),
            ]
        },
    )
    usar([("BACKUP", "/respaldos")], entorno)

    respuesta = cliente.get("/directorios/respaldos", headers=CABECERAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["avisos"] == []
    assert cuerpo["respaldos"] == [
        {
            "directorio": "BACKUP",
            "ruta": "/respaldos",
            "base": "hr_20240301_100000",
            "tipo": "Data Pump",
            "estado": "Completo",
            "archivos": [
                {"nombre": "hr_20240301_100000.dmp", "tamano": 200},
                {"nombre": "hr_20240301_100000.log", "tamano": 7},
            ],
            "tamano": 207,
            "fecha": "2024-03-01T10:00:00",
        },
        {
            "directorio": "BACKUP",
            "ruta": "/respaldos",
            "base": "hr_20240101_100000",
            "tipo": "Data Pump",
            "estado": "Completo",
            "archivos": [
                {"nombre": "hr_20240101_100000.dmp", "tamano": 100},
                {"nombre": "hr_20240101_100000.log", "tamano": 5},
            ],
            "tamano": 105,
            "fecha": "2024-01-01T10:00:00",
        },
    ]


def test_sin_directorios_responde_listas_vacias(cliente):
    usar([], EntornoFalso())

    respuesta = cliente.get("/directorios/respaldos", headers=CABECERAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"respaldos": [], "avisos": []}


def test_un_directorio_ilegible_se_refleja_en_avisos(cliente):
    usar([("BACKUP", "/respaldos")], EntornoFalso(fallo_listado="permiso denegado"))

    respuesta = cliente.get("/directorios/respaldos", headers=CABECERAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["respaldos"] == []
    assert len(cuerpo["avisos"]) == 1
    assert "BACKUP" in cuerpo["avisos"][0]


def test_sin_sysdba_ni_dba_responde_403(cliente):
    usar([("BACKUP", "/respaldos")], EntornoFalso(), roles=())

    respuesta = cliente.get("/directorios/respaldos", headers=CABECERAS)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "Se requiere sesión SYSDBA o rol DBA"}


def test_con_sesion_sysdba_pasa_sin_rol_dba(cliente):
    usar([], EntornoFalso(), roles=(), sysdba=True)

    assert cliente.get("/directorios/respaldos", headers=CABECERAS).status_code == 200


def test_sin_sesion_responde_401(cliente):
    assert cliente.get("/directorios/respaldos").status_code == 401


def test_la_ruta_respaldos_no_pisa_put_ni_delete_de_directorios(cliente):
    class Sentencia:
        def __init__(self):
            self.sqls = []

        def __call__(self, sql, params=None):
            self.sqls.append(sql)

    sentencia = Sentencia()
    usar([("BACKUP", "/respaldos")], EntornoFalso())
    app.dependency_overrides[obtener_sentencia] = lambda: sentencia

    editado = cliente.put("/directorios/backup", json={"ruta": "/otra"}, headers=CABECERAS)
    eliminado = cliente.delete("/directorios/backup", headers=CABECERAS)

    assert editado.json() == {"mensaje": "Directorio BACKUP actualizado"}
    assert eliminado.json() == {"mensaje": "Directorio BACKUP eliminado"}
