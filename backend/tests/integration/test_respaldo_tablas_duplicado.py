from datetime import datetime

import pytest

from tests.integration.conftest import cabeceras, docker

pytestmark = pytest.mark.integration

DMP = "duplicado_20261017_153045.dmp"


class FechaFija(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 17, 15, 30, 45)


def huella(ruta: str) -> str:
    resultado = docker("md5sum", ruta)
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout.split()[0]


def test_un_segundo_respaldo_con_el_mismo_nombre_falla_sin_sobrescribir_el_dmp(
    cliente, entorno, monkeypatch
):
    monkeypatch.setattr("src.api.respaldos.datetime", FechaFija)
    solicitud = {
        "tablas": [entorno.tabla],
        "directorio": entorno.directorio,
        "nombre": "duplicado",
    }

    primero = cliente.post("/respaldos/tablas", json=solicitud, headers=cabeceras(entorno))
    assert primero.status_code == 200, primero.text
    assert primero.json()["dmp"] == DMP
    ruta_dmp = f"{entorno.ruta}/{DMP}"
    huella_original = huella(ruta_dmp)

    segundo = cliente.post("/respaldos/tablas", json=solicitud, headers=cabeceras(entorno))

    assert segundo.status_code == 500
    cuerpo = segundo.json()
    assert "ORA-27038" in cuerpo["log"]
    assert cuerpo["explicacion"] == (
        "Ya existe un archivo de respaldo con ese nombre en el directorio"
    )
    assert "terminó con código" in cuerpo["mensaje"]
    assert entorno.password not in segundo.text
    assert huella(ruta_dmp) == huella_original
    sobrantes = docker("sh", "-c", "ls /tmp/expdp_*.par 2>/dev/null")
    assert sobrantes.stdout.strip() == "", "quedó un parfile con la contraseña en el contenedor"
