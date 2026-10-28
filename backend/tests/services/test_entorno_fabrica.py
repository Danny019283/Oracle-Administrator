from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from src.services import entorno_fabrica
from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_fabrica import ConfiguracionInvalida, fabrica_desde_variables
from src.services.entorno_local import EntornoLocal
from src.services.entorno_oracle import Salida


@pytest.fixture
def comandos(monkeypatch):
    """Sustituye el lanzador de procesos y anota los comandos que emite la estrategia."""
    emitidos = []

    def falso(args, entrada=None, variables=None):
        emitidos.append(args)
        return Salida(codigo=0, texto="")

    monkeypatch.setattr(entorno_fabrica, "ejecutar_proceso", falso)
    return emitidos


def test_sin_variables_crea_contenedor_con_docker_y_oracle21c(comandos):
    entorno = fabrica_desde_variables({}, "linux")

    entorno.leer_archivo(PurePosixPath("/x.log"))

    assert isinstance(entorno, EntornoContenedor)
    assert comandos == [["docker", "exec", "oracle21c", "cat", "/x.log"]]


def test_contenedor_con_podman_y_contenedor_indicados(comandos):
    variables = {
        "ORACLE_ENTORNO": "contenedor",
        "ORACLE_CONTAINER_CLI": "podman",
        "ORACLE_CONTAINER": "miora",
    }

    fabrica_desde_variables(variables, "win32").leer_archivo(PurePosixPath("/x.log"))

    assert comandos == [["podman", "exec", "miora", "cat", "/x.log"]]


def test_local_en_linux_usa_rutas_path():
    entorno = fabrica_desde_variables({"ORACLE_ENTORNO": "local"}, "linux")

    assert isinstance(entorno, EntornoLocal)
    assert entorno.tipo_ruta is Path


def test_local_en_windows_usa_rutas_de_windows():
    entorno = fabrica_desde_variables({"ORACLE_ENTORNO": "local"}, "win32")

    assert isinstance(entorno, EntornoLocal)
    assert entorno.tipo_ruta is PureWindowsPath


def test_entorno_desconocido_indica_los_valores_validos():
    with pytest.raises(ConfiguracionInvalida) as error:
        fabrica_desde_variables({"ORACLE_ENTORNO": "nube"}, "linux")

    mensaje = str(error.value)
    assert "ORACLE_ENTORNO" in mensaje
    assert "contenedor" in mensaje
    assert "local" in mensaje


def test_cli_desconocido_indica_los_valores_validos():
    with pytest.raises(ConfiguracionInvalida) as error:
        fabrica_desde_variables({"ORACLE_CONTAINER_CLI": "nerdctl"}, "linux")

    mensaje = str(error.value)
    assert "ORACLE_CONTAINER_CLI" in mensaje
    assert "docker" in mensaje
    assert "podman" in mensaje
