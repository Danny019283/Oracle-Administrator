import oracledb
import pytest

from tests.integration.conftest import (
    HOST,
    PUERTO,
    _password_admin,
    cabeceras,
    docker,
)
from tests.integration.test_respaldo_full_oracle import esperar_a_que_oracle_responda, login_admin

pytestmark = pytest.mark.integration


@pytest.fixture
def admin(cliente, entorno):
    if _password_admin() is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para iniciar sesión como SYSDBA")
    cabecera = login_admin(cliente, entorno)
    if not cliente.get("/respaldos/full/estado", headers=cabecera).json()["archivelog"]:
        activado = cliente.post("/respaldos/full/archivelog", headers=cabecera)
        assert activado.status_code == 200, activado.text
        esperar_a_que_oracle_responda(_password_admin())
        cabecera = login_admin(cliente, entorno)
    return cabecera


def _listar(cliente, admin, entorno, prefijo):
    respuesta = cliente.get("/directorios/respaldos", headers=admin)
    assert respuesta.status_code == 200, respuesta.text
    return [
        r
        for r in respuesta.json()["respaldos"]
        if r["directorio"] == entorno.directorio and r["base"].startswith(prefijo)
    ]


def _archivos(entorno, prefijo):
    salida = docker("ls", entorno.ruta)
    assert salida.returncode == 0, salida.stderr
    return [a for a in salida.stdout.split() if a.startswith(prefijo)]


def _estados_de_piezas(entorno, prefijo):
    """Estado en V$BACKUP_PIECE de las piezas de esta base: A disponible, X expirada, D borrada."""
    with oracledb.connect(
        user="sys", password=_password_admin(), dsn=f"{HOST}:{PUERTO}/XE", mode=oracledb.AUTH_MODE_SYSDBA
    ) as bd:
        cursor = bd.cursor()
        cursor.execute("SELECT status FROM v$backup_piece WHERE handle LIKE :h", h=f"{entorno.ruta}/{prefijo}%")
        return {fila[0] for fila in cursor.fetchall()}


def test_un_respaldo_data_pump_real_se_lista_completo_y_se_elimina(cliente, entorno, admin):
    prefijo = "admresp_dmp_"
    creado = cliente.post(
        "/respaldos/schemas",
        json={"schemas": [entorno.usuario], "directorio": entorno.directorio, "nombre": "admresp_dmp"},
        headers=cabeceras(entorno),
    )
    assert creado.status_code == 200, creado.text

    try:
        [respaldo] = _listar(cliente, admin, entorno, prefijo)
        assert respaldo["tipo"] == "Data Pump"
        assert respaldo["estado"] == "Completo"
        assert respaldo["ruta"] == entorno.ruta
        assert {a["nombre"].rsplit(".", 1)[1] for a in respaldo["archivos"]} == {"dmp", "log"}

        eliminado = cliente.delete(
            f"/directorios/{entorno.directorio}/respaldos/{respaldo['base']}", headers=admin
        )

        assert eliminado.status_code == 200, eliminado.text
        assert eliminado.json()["advertencia"] is None
        assert _archivos(entorno, prefijo) == []
        assert _listar(cliente, admin, entorno, prefijo) == []
    finally:
        docker("sh", "-c", f"rm -f {entorno.ruta}/{prefijo}*")


def test_un_respaldo_full_real_deja_piezas_dbf_y_log_se_lista_completo_y_se_elimina_sin_piezas_expiradas(
    cliente, entorno, admin
):
    prefijo = "admresp_full_"
    full = cliente.post(
        "/respaldos/full",
        json={"directorio": entorno.directorio, "nombre": "admresp_full"},
        headers=admin,
    )
    assert full.status_code == 200, full.text

    try:
        archivos = _archivos(entorno, prefijo)
        assert any(a.endswith(".dbf") for a in archivos), archivos
        assert any(a.endswith(".log") for a in archivos), archivos  # RMAN escribió el log con log=

        [respaldo] = _listar(cliente, admin, entorno, prefijo)
        assert respaldo["tipo"] == "RMAN"
        assert respaldo["estado"] == "Completo"
        assert respaldo["ruta"] == entorno.ruta
        assert all(a["tamano"] > 0 for a in respaldo["archivos"]), respaldo["archivos"]  # el log no queda en 0 bytes
        assert sorted(a["nombre"] for a in respaldo["archivos"]) == sorted(archivos)
        assert "A" in _estados_de_piezas(entorno, prefijo)

        eliminado = cliente.delete(
            f"/directorios/{entorno.directorio}/respaldos/{respaldo['base']}", headers=admin
        )

        assert eliminado.status_code == 200, eliminado.text
        assert eliminado.json()["advertencia"] is None, eliminado.json()["advertencia"]
        assert _archivos(entorno, prefijo) == []
        assert _estados_de_piezas(entorno, prefijo) <= {"D"}  # ni disponibles ni expiradas
    finally:
        docker("sh", "-c", f"rm -f {entorno.ruta}/{prefijo}*")
