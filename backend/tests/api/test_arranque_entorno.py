import importlib

import pytest

import main
from src.api.dependencias import obtener_entorno
from src.api.sesion import SolicitudSesion
from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_fabrica import ConfiguracionInvalida


def test_el_entorno_se_construye_al_cargar_main_y_obtener_entorno_devuelve_siempre_la_misma_instancia():
    assert obtener_entorno() is obtener_entorno()
    assert obtener_entorno() is main.entorno


def test_sin_variables_el_entorno_es_el_contenedor_docker(monkeypatch):
    monkeypatch.delenv("ORACLE_ENTORNO", raising=False)
    importlib.reload(main)
    assert isinstance(obtener_entorno(), EntornoContenedor)


def test_con_un_valor_invalido_la_carga_de_main_falla_con_el_mensaje_de_configuracion(monkeypatch):
    monkeypatch.setenv("ORACLE_ENTORNO", "nube")
    with pytest.raises(ConfiguracionInvalida, match="ORACLE_ENTORNO.*nube.*contenedor, local"):
        importlib.reload(main)


def test_el_entorno_no_es_un_campo_del_login():
    assert not any("entorno" in campo for campo in SolicitudSesion.model_fields)
