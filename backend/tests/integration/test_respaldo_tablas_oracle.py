import re
import tomllib
from pathlib import Path

import pytest

from tests.integration.conftest import cabeceras, docker


def test_las_pruebas_de_integracion_no_corren_en_el_comando_normal():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    opciones = tomllib.loads(pyproject.read_text())["tool"]["pytest"]["ini_options"]

    assert any(m.startswith("integration:") for m in opciones["markers"])
    assert "not integration" in opciones["addopts"]


@pytest.mark.integration
def test_lista_solo_las_tablas_del_usuario_conectado(cliente, entorno):
    respuesta = cliente.get("/respaldos/tablas", headers=cabeceras(entorno))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tablas": [entorno.tabla]}


@pytest.mark.integration
def test_lista_los_directorios_con_read_y_write_y_su_ruta_fisica(cliente, entorno):
    respuesta = cliente.get("/respaldos/directorios", headers=cabeceras(entorno))

    assert respuesta.status_code == 200
    directorios = respuesta.json()["directorios"]
    assert {"nombre": entorno.directorio, "ruta": entorno.ruta} in directorios
    assert "ORACLE_HOME" not in [d["nombre"] for d in directorios]


@pytest.mark.integration
def test_respalda_una_tabla_y_deja_el_dmp_y_el_log_en_el_directorio(cliente, entorno):
    solicitud = {
        "tablas": [entorno.tabla],
        "directorio": entorno.directorio,
        "nombre": "integracion",
    }

    respuesta = cliente.post("/respaldos/tablas", json=solicitud, headers=cabeceras(entorno))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert re.fullmatch(r"integracion_\d{8}_\d{6}\.dmp", cuerpo["dmp"])
    assert docker("ls", f"{entorno.ruta}/{cuerpo['dmp']}").returncode == 0
    assert docker("ls", f"{entorno.ruta}/{cuerpo['log']}").returncode == 0
    assert entorno.password not in respuesta.text
