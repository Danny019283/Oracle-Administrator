import re
from collections.abc import Callable, Sequence
from typing import Any

from src.services.identificadores import normalizar_identificador
from src.services.oracle_ejecucion import Sentencia, Sesion
from src.services.tablespaces import listar_tablespaces

Consulta = Callable[..., Sequence[Sequence[Any]]]

SQL_SCHEMAS = "SELECT username FROM dba_users WHERE oracle_maintained = 'N' ORDER BY username"

SQL_TABLAS = """
SELECT table_name, num_rows, blocks, avg_row_len,
       TO_CHAR(last_analyzed, 'DD/MM/YYYY HH24:MI:SS'), stale_stats
FROM dba_tab_statistics
WHERE owner = :schema AND object_type = 'TABLE' AND table_name NOT LIKE 'BIN$%'
ORDER BY table_name
"""

SQL_COLUMNAS = """
SELECT column_name, data_type FROM dba_tab_columns
WHERE owner = :schema AND table_name = :tabla
ORDER BY column_id
"""

# Índices de la tabla con sus columnas en orden y, si respalda una llave
# primaria o única, el nombre de esa restricción (esos no se pueden eliminar).
SQL_INDICES = """
SELECT i.owner, i.index_name, i.uniqueness, i.index_type, i.status, i.tablespace_name,
       TO_CHAR(i.last_analyzed, 'DD/MM/YYYY HH24:MI:SS'), i.distinct_keys, i.blevel,
       (SELECT LISTAGG(c.column_name, ', ') WITHIN GROUP (ORDER BY c.column_position)
        FROM dba_ind_columns c
        WHERE c.index_owner = i.owner AND c.index_name = i.index_name),
       (SELECT MAX(k.constraint_name) FROM dba_constraints k
        WHERE k.index_owner = i.owner AND k.index_name = i.index_name
          AND k.constraint_type IN ('P', 'U'))
FROM dba_indexes i
WHERE i.table_owner = :schema AND i.table_name = :tabla AND i.index_type <> 'LOB'
ORDER BY i.index_name
"""

# PLAN_TABLE es una tabla temporal de la sesión: EXPLAIN PLAN y estas lecturas
# tienen que ir en la misma conexión.
SQL_PLAN_TEXTO = "SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', NULL, 'TYPICAL'))"

SQL_PLAN_FILAS = """
SELECT id, parent_id, depth, operation, options, object_owner, object_name,
       cost, cardinality, bytes, access_predicates, filter_predicates
FROM plan_table ORDER BY id
"""

SQL_ESTADISTICAS_TABLA = """
BEGIN
  DBMS_STATS.GATHER_TABLE_STATS(ownname => :schema, tabname => :tabla, cascade => TRUE);
END;
"""

SQL_ESTADISTICAS_SCHEMA = """
BEGIN
  DBMS_STATS.GATHER_SCHEMA_STATS(ownname => :schema, cascade => TRUE);
END;
"""

_SENTENCIA_EXPLICABLE = re.compile(r"(SELECT|WITH|INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
_COLUMNA_SIMPLE = re.compile(r"[A-Z][A-Z0-9_$#]{0,127}")
MAXIMO_SQL = 20000
MAXIMO_COLUMNAS_INDICE = 32


class SolicitudTuningInvalida(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


class ObjetoNoEncontrado(Exception):
    pass


def listar_schemas(consulta: Consulta) -> list[str]:
    return [fila[0] for fila in consulta(SQL_SCHEMAS)]


def tablespaces_para_indices(consulta: Consulta) -> list[str]:
    return [
        t["nombre"]
        for t in listar_tablespaces(consulta)
        if t["tipo"] == "PERMANENT" and t["estado"] == "ONLINE"
    ]


def catalogos(consulta: Consulta) -> dict[str, list[str]]:
    return {"schemas": listar_schemas(consulta), "tablespaces": tablespaces_para_indices(consulta)}


def _schema(consulta: Consulta, schema: str) -> str:
    """Solo se trabaja sobre schemas creados por personas (no los de Oracle)."""
    nombre = normalizar_identificador(schema, "el schema")
    if nombre not in listar_schemas(consulta):
        raise ObjetoNoEncontrado(f"El schema {nombre} no existe o es un schema interno de Oracle")
    return nombre


def listar_tablas(consulta: Consulta, schema: str) -> list[dict[str, Any]]:
    schema = _schema(consulta, schema)
    return [
        {
            "tabla": tabla,
            "filas": filas,
            "bloques": bloques,
            "largo_promedio": largo,
            "analizada": analizada,
            "obsoletas": obsoletas == "YES",
        }
        for tabla, filas, bloques, largo, analizada, obsoletas in consulta(
            SQL_TABLAS, {"schema": schema}
        )
    ]


def _tabla(consulta: Consulta, schema: str, tabla: str) -> tuple[str, str]:
    schema = _schema(consulta, schema)
    nombre = normalizar_identificador(tabla, "la tabla")
    if nombre not in {t["tabla"] for t in listar_tablas(consulta, schema)}:
        raise ObjetoNoEncontrado(f"La tabla {schema}.{nombre} no existe")
    return schema, nombre


def listar_columnas(consulta: Consulta, schema: str, tabla: str) -> list[dict[str, str]]:
    schema, tabla = _tabla(consulta, schema, tabla)
    return [
        {"nombre": nombre, "tipo": tipo}
        for nombre, tipo in consulta(SQL_COLUMNAS, {"schema": schema, "tabla": tabla})
    ]


def listar_indices(consulta: Consulta, schema: str, tabla: str) -> list[dict[str, Any]]:
    schema, tabla = _tabla(consulta, schema, tabla)
    return [
        {
            "propietario": propietario,
            "nombre": nombre,
            "unico": unicidad == "UNIQUE",
            "tipo": tipo,
            "estado": estado,
            "tablespace": tablespace,
            "analizado": analizado,
            "claves_distintas": distintas,
            "niveles": niveles,
            "columnas": columnas or "",
            "restriccion": restriccion,
        }
        for (
            propietario, nombre, unicidad, tipo, estado, tablespace,
            analizado, distintas, niveles, columnas, restriccion,
        ) in consulta(SQL_INDICES, {"schema": schema, "tabla": tabla})
    ]


def recolectar_estadisticas(
    consulta: Consulta, sentencia: Sentencia, schema: str, tabla: str = ""
) -> str:
    """Regenera estadísticas de una tabla (con sus índices) o de todo el schema."""
    if (tabla or "").strip():
        schema, tabla = _tabla(consulta, schema, tabla)
        sentencia(SQL_ESTADISTICAS_TABLA, {"schema": schema, "tabla": tabla})
        return f"{schema}.{tabla}"
    schema = _schema(consulta, schema)
    sentencia(SQL_ESTADISTICAS_SCHEMA, {"schema": schema})
    return schema


def _observaciones(operaciones: list[dict[str, Any]], texto: list[str]) -> list[str]:
    """Pistas en lenguaje natural sobre lo que suele empeorar un plan."""
    observaciones = []
    for op in operaciones:
        if op["operacion"] == "TABLE ACCESS" and (op["opciones"] or "").startswith("FULL"):
            observaciones.append(
                f"Se lee completa la tabla {op['objeto']} (TABLE ACCESS FULL). Si la consulta "
                "filtra pocas filas, un índice sobre las columnas del WHERE puede ayudar."
            )
        if op["operacion"] == "MERGE JOIN" and op["opciones"] == "CARTESIAN":
            observaciones.append(
                "Hay un producto cartesiano (MERGE JOIN CARTESIAN): revisa que todas las "
                "tablas estén unidas con una condición."
            )
    if any("dynamic statistics used" in linea or "dynamic sampling used" in linea for linea in texto):
        observaciones.append(
            "Oracle no encontró estadísticas de alguna tabla y las estimó al vuelo; "
            "genéralas en la sección Estadísticas para obtener un plan más fiable."
        )
    return observaciones


def plan_ejecucion(consulta: Consulta, sesion: Sesion, sql: str, schema: str = "") -> dict[str, Any]:
    """Obtiene el plan de ejecución sin ejecutar la sentencia (EXPLAIN PLAN)."""
    sql = (sql or "").strip().rstrip(";").strip()
    errores = []
    if not sql:
        errores.append("Debes escribir la consulta que quieres analizar")
    elif not _SENTENCIA_EXPLICABLE.match(sql):
        errores.append("Solo se pueden analizar sentencias SELECT, WITH, INSERT, UPDATE, DELETE o MERGE")
    if len(sql) > MAXIMO_SQL:
        errores.append(f"La consulta no puede superar los {MAXIMO_SQL} caracteres")
    if errores:
        raise SolicitudTuningInvalida(errores)

    pasos: list[tuple[str, dict[str, Any] | None]] = []
    if (schema or "").strip():
        pasos.append((f"ALTER SESSION SET CURRENT_SCHEMA = {_schema(consulta, schema)}", None))
    pasos += [(f"EXPLAIN PLAN FOR {sql}", None), (SQL_PLAN_TEXTO, None), (SQL_PLAN_FILAS, None)]
    *_, texto_filas, plan_filas = sesion(pasos)

    texto = [fila[0] for fila in texto_filas or []]
    operaciones = [
        {
            "id": id_,
            "padre": padre,
            "nivel": nivel,
            "operacion": operacion,
            "opciones": opciones,
            "propietario": propietario,
            "objeto": objeto,
            "costo": costo,
            "filas": filas,
            "bytes": bytes_,
            "acceso": acceso,
            "filtro": filtro,
        }
        for (
            id_, padre, nivel, operacion, opciones, propietario, objeto,
            costo, filas, bytes_, acceso, filtro,
        ) in plan_filas or []
    ]
    return {
        "texto": texto,
        "operaciones": operaciones,
        "observaciones": _observaciones(operaciones, texto),
    }


def crear_indice(
    consulta: Consulta,
    sentencia: Sentencia,
    schema: str,
    tabla: str,
    nombre: str,
    columnas: list[str],
    unico: bool = False,
    tablespace: str = "",
) -> str:
    schema, tabla = _tabla(consulta, schema, tabla)
    errores = []
    try:
        nombre = normalizar_identificador(nombre, "el índice")
    except ValueError as error:
        errores.append(str(error))

    disponibles = {c["nombre"] for c in listar_columnas(consulta, schema, tabla)}
    elegidas = [c.strip().upper() for c in columnas if c and c.strip()]
    if not elegidas:
        errores.append("Debes elegir al menos una columna")
    for columna in elegidas:
        if columna not in disponibles:
            errores.append(f"La columna {columna} no existe en {schema}.{tabla}")
        elif not _COLUMNA_SIMPLE.fullmatch(columna):
            # Columnas creadas entre comillas ("Mi Columna") no se concatenan en el DDL.
            errores.append(f"La columna {columna} tiene un nombre que no se puede indexar desde aquí")
    if len(set(elegidas)) != len(elegidas):
        errores.append("No puedes repetir una columna en el mismo índice")
    if len(elegidas) > MAXIMO_COLUMNAS_INDICE:
        errores.append(f"Un índice admite como máximo {MAXIMO_COLUMNAS_INDICE} columnas")

    tablespace = (tablespace or "").strip().upper()
    if tablespace and tablespace not in tablespaces_para_indices(consulta):
        errores.append("Debes elegir un tablespace permanente y ONLINE")
    if errores:
        raise SolicitudTuningInvalida(errores)

    sql = (
        f"CREATE {'UNIQUE ' if unico else ''}INDEX {schema}.{nombre} "
        f"ON {schema}.{tabla} ({', '.join(elegidas)})"
    )
    if tablespace:
        sql += f" TABLESPACE {tablespace}"
    sentencia(sql)
    return f"{schema}.{nombre}"


def eliminar_indice(
    consulta: Consulta, sentencia: Sentencia, schema: str, tabla: str, nombre: str
) -> str:
    nombre = normalizar_identificador(nombre, "el índice")
    indice = next((i for i in listar_indices(consulta, schema, tabla) if i["nombre"] == nombre), None)
    if indice is None:
        raise ObjetoNoEncontrado(f"El índice {nombre} no existe en esa tabla")
    if indice["restriccion"]:
        raise SolicitudTuningInvalida(
            [
                f"El índice {nombre} respalda la restricción {indice['restriccion']} "
                "(llave primaria o única) y no se puede eliminar"
            ]
        )
    sentencia(f"DROP INDEX {indice['propietario']}.{nombre}")
    return f"{indice['propietario']}.{nombre}"
