from collections.abc import Callable, Sequence
import re
from dataclasses import dataclass
from pathlib import PurePath, PureWindowsPath
from typing import Any

from src.services.entorno_oracle import EntornoOracle
from src.services.instancia import sid_de_instancia
from src.services.identificadores import IdentificadorInvalido, normalizar_identificador
from src.services.oracle_ejecucion import Sentencia

Consulta = Callable[..., Sequence[Sequence[Any]]]

_SQL = """
SELECT d.directory_name, d.directory_path
FROM all_directories d
WHERE EXISTS (SELECT 1 FROM all_tab_privs p
              WHERE p.table_name = d.directory_name AND p.privilege = 'READ')
  AND EXISTS (SELECT 1 FROM all_tab_privs p
              WHERE p.table_name = d.directory_name AND p.privilege = 'WRITE')
ORDER BY d.directory_name
"""

_SQL_TODOS = """
SELECT directory_name, directory_path
FROM all_directories
ORDER BY directory_name
"""

_SQL_SCHEMA = "SELECT username FROM all_users WHERE username = :schema"


class SinDirectorios(Exception):
    pass


class DirectorioInvalido(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


class DirectorioNoEncontrado(Exception):
    pass


@dataclass(frozen=True)
class Directorio:
    nombre: str
    ruta: str


def listar_directorios(consulta: Consulta) -> list[Directorio]:
    filas = consulta(_SQL)
    if not filas:
        raise SinDirectorios(
            "No hay directorios disponibles. Debes crear uno desde esta pantalla para poder respaldar"
        )
    return [Directorio(nombre=nombre, ruta=ruta) for nombre, ruta in filas]


def listar_todos_directorios(consulta: Consulta) -> list[Directorio]:
    return [Directorio(nombre=nombre, ruta=ruta) for nombre, ruta in consulta(_SQL_TODOS)]


DIRECTORIOS_DEL_SISTEMA = {"DATA_PUMP_DIR"}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def validar_ruta(ruta: str, tipo_ruta: type[PurePath]) -> list[str]:
    if not ruta:
        return ["La ruta es obligatoria"]
    errores = []
    if not tipo_ruta(ruta).is_absolute():
        errores.append("La ruta debe ser absoluta")
    if len(ruta) > 4000:
        errores.append("La ruta no puede superar los 4000 caracteres")
    if "'" in ruta:
        errores.append("La ruta no puede contener comillas simples")
    if _CONTROL.search(ruta):
        errores.append("La ruta no puede contener caracteres de control")
    return errores


def ejemplos_ruta(tipo_ruta: type[PurePath]) -> list[str]:
    if issubclass(tipo_ruta, PureWindowsPath):
        return ["C:\\respaldos", "\\\\servidor\\recurso"]
    return ["/opt/oracle/respaldos"]


def crear_directorio(
    consulta: Consulta,
    sentencia: Sentencia,
    entorno: EntornoOracle,
    nombre: str,
    ruta: str,
    schema: str | None = None,
) -> str:
    errores = []
    try:
        nombre = normalizar_identificador(nombre, "el directorio")
    except IdentificadorInvalido as error:
        errores.append(str(error))
    errores += validar_ruta(ruta, entorno.tipo_ruta)
    if schema:
        try:
            schema = normalizar_identificador(schema, "el schema")
        except IdentificadorInvalido as error:
            errores.append(str(error))
    if not errores and any(d.nombre == nombre for d in listar_todos_directorios(consulta)):
        errores.append(f"Ya existe un directorio llamado {nombre}")
    if not errores and schema and not consulta(_SQL_SCHEMA, {"schema": schema}):
        errores.append(f"No existe el schema {schema}")
    if errores:
        raise DirectorioInvalido(errores)

    entorno.dar_permisos_a_oracle(ruta, sid_de_instancia(consulta))
    sentencia(f"CREATE DIRECTORY {nombre} AS '{ruta}'")
    if schema:
        sentencia(f"GRANT READ, WRITE ON DIRECTORY {nombre} TO {schema}")
    return nombre


def _exigir_modificable(consulta: Consulta, nombre: str) -> None:
    if nombre not in {d.nombre for d in listar_todos_directorios(consulta)}:
        raise DirectorioNoEncontrado(f"No existe el directorio {nombre}")
    if nombre in DIRECTORIOS_DEL_SISTEMA:
        raise DirectorioInvalido([f"El directorio {nombre} no se puede editar ni eliminar"])


def editar_directorio(
    consulta: Consulta,
    sentencia: Sentencia,
    entorno: EntornoOracle,
    nombre: str,
    ruta: str,
) -> None:
    errores = []
    try:
        nombre = normalizar_identificador(nombre, "el directorio")
    except IdentificadorInvalido as error:
        errores.append(str(error))
    errores += validar_ruta(ruta, entorno.tipo_ruta)
    if errores:
        raise DirectorioInvalido(errores)
    _exigir_modificable(consulta, nombre)

    entorno.dar_permisos_a_oracle(ruta, sid_de_instancia(consulta))
    sentencia(f"CREATE OR REPLACE DIRECTORY {nombre} AS '{ruta}'")


def eliminar_directorio(consulta: Consulta, sentencia: Sentencia, nombre: str) -> None:
    try:
        nombre = normalizar_identificador(nombre, "el directorio")
    except IdentificadorInvalido as error:
        raise DirectorioInvalido([str(error)])
    _exigir_modificable(consulta, nombre)
    sentencia(f"DROP DIRECTORY {nombre}")
