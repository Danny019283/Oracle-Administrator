from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from src.services import entorno_fabrica
from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_fabrica import (
    ConfiguracionInvalida,
    fabrica_desde_variables,
    fra_desde_variables,
    programador_desde_variables,
)
from src.services.entorno_local import EntornoLocal
from src.services.entorno_oracle import Salida
from src.services.programador_tareas import (
    ProgramadorCron,
    ProgramadorCronContenedor,
    ProgramadorSchtasks,
)


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


def test_la_fra_en_contenedor_toma_la_variable_como_ruta_posix():
    variables = {"ORACLE_FRA_DIRECTORIO": "/u01/fra"}

    fra = fra_desde_variables(variables, fabrica_desde_variables(variables, "win32"))

    assert fra == PurePosixPath("/u01/fra")
    assert isinstance(fra, PurePosixPath)


def test_la_fra_en_contenedor_sin_variable_es_la_de_hoy():
    entorno = fabrica_desde_variables({}, "linux")

    assert fra_desde_variables({}, entorno) == PurePosixPath(
        "/opt/oracle/oradata/fast_recovery_area"
    )


def test_la_fra_en_local_linux_toma_la_variable_como_path():
    variables = {"ORACLE_ENTORNO": "local", "ORACLE_FRA_DIRECTORIO": "/u01/fra"}

    fra = fra_desde_variables(variables, fabrica_desde_variables(variables, "linux"))

    assert fra == Path("/u01/fra")
    assert isinstance(fra, Path)


def test_la_fra_en_local_windows_toma_la_variable_como_ruta_de_windows():
    variables = {"ORACLE_ENTORNO": "local", "ORACLE_FRA_DIRECTORIO": "D:\\oracle\\fra"}

    fra = fra_desde_variables(variables, fabrica_desde_variables(variables, "win32"))

    assert fra == PureWindowsPath("D:\\oracle\\fra")


@pytest.mark.parametrize("variables", [{"ORACLE_ENTORNO": "local"}, {"ORACLE_ENTORNO": "local", "ORACLE_FRA_DIRECTORIO": ""}])
def test_la_fra_en_local_sin_variable_no_tiene_defecto(variables):
    assert fra_desde_variables(variables, fabrica_desde_variables(variables, "linux")) is None


def test_programador_sin_variables_es_cron_del_contenedor_con_docker_y_oracle21c(comandos):
    programador = programador_desde_variables({}, "linux")

    programador.eliminar(1)

    assert isinstance(programador, ProgramadorCronContenedor)
    assert comandos[0][:5] == ["docker", "exec", "-u", "root", "oracle21c"]


def test_programador_contenedor_con_podman_y_contenedor_indicados(comandos):
    variables = {"ORACLE_CONTAINER_CLI": "podman", "ORACLE_CONTAINER": "miora"}

    programador_desde_variables(variables, "win32").eliminar(1)

    assert comandos[0][:5] == ["podman", "exec", "-u", "root", "miora"]


def test_programador_local_en_linux_es_cron():
    programador = programador_desde_variables({"ORACLE_ENTORNO": "local"}, "linux")

    assert type(programador) is ProgramadorCron


def test_programador_local_en_windows_es_schtasks():
    programador = programador_desde_variables({"ORACLE_ENTORNO": "local"}, "win32")

    assert isinstance(programador, ProgramadorSchtasks)


def test_programador_entorno_desconocido_indica_los_valores_validos():
    with pytest.raises(ConfiguracionInvalida, match="ORACLE_ENTORNO.*nube.*contenedor, local"):
        programador_desde_variables({"ORACLE_ENTORNO": "nube"}, "linux")


def test_programador_cli_desconocido_indica_los_valores_validos():
    with pytest.raises(ConfiguracionInvalida, match="ORACLE_CONTAINER_CLI.*nerdctl.*docker, podman"):
        programador_desde_variables({"ORACLE_CONTAINER_CLI": "nerdctl"}, "linux")
