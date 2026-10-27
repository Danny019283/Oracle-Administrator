from collections.abc import Callable, Sequence
from typing import Any

from src.services.identificadores import normalizar_identificador
from src.services.oracle_ejecucion import Sentencia

Consulta = Callable[..., Sequence[Sequence[Any]]]

ACCIONES_TABLA = ("SELECT", "INSERT", "UPDATE", "DELETE")
ACCIONES_SESION = ("LOGON", "LOGOFF")

SQL_MODO = "SELECT value FROM v$option WHERE parameter = 'Unified Auditing'"
SQL_AUDIT_TRAIL = "SELECT value FROM v$parameter WHERE name = 'audit_trail'"

SQL_POLITICAS = """
SELECT policy_name, audit_option, object_schema, object_name
FROM audit_unified_policies
ORDER BY policy_name, audit_option
"""

SQL_HABILITADAS = "SELECT DISTINCT policy_name FROM audit_unified_enabled_policies"

SQL_TABLAS = """
SELECT owner, table_name FROM dba_tables
WHERE owner IN (SELECT username FROM dba_users WHERE oracle_maintained = 'N')
ORDER BY owner, table_name
"""


class PoliticaInvalida(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


def estado(consulta: Consulta) -> dict[str, Any]:
    modo = consulta(SQL_MODO)
    trail = consulta(SQL_AUDIT_TRAIL)
    pura = bool(modo) and str(modo[0][0]).upper() == "TRUE"
    return {
        "modo": "Auditoría unificada pura" if pura else "Modo mixto (unificada y tradicional)",
        "audit_trail": trail[0][0] if trail else None,
    }


def listar_politicas(consulta: Consulta) -> list[dict[str, Any]]:
    habilitadas = {fila[0] for fila in consulta(SQL_HABILITADAS)}
    politicas: dict[str, dict[str, Any]] = {}
    for nombre, opcion, schema, objeto in consulta(SQL_POLITICAS):
        politica = politicas.setdefault(
            nombre,
            {
                "nombre": nombre,
                "acciones": [],
                "objetos": [],
                "habilitada": nombre in habilitadas,
                "predefinida": nombre.startswith("ORA_"),
            },
        )
        if opcion and opcion not in politica["acciones"]:
            politica["acciones"].append(opcion)
        if schema and objeto and schema != "NONE" and objeto != "NONE":
            completo = f"{schema}.{objeto}"
            if completo not in politica["objetos"]:
                politica["objetos"].append(completo)
    return list(politicas.values())


def listar_tablas_auditables(consulta: Consulta) -> list[dict[str, str]]:
    return [{"schema": s, "tabla": t} for s, t in consulta(SQL_TABLAS)]


def construir_politica(
    nombre: str, tipo: str, acciones: list[str], schema: str = "", tabla: str = ""
) -> tuple[str, str]:
    """Valida la solicitud y devuelve (nombre normalizado, sentencia CREATE)."""
    errores = []
    try:
        nombre = normalizar_identificador(nombre, "la política")
        if nombre.startswith("ORA_"):
            errores.append("El prefijo ORA_ está reservado para las políticas de Oracle")
    except ValueError as error:
        errores.append(str(error))

    acciones = [a.upper() for a in acciones]
    sentencia = ""
    if tipo == "tabla":
        if not acciones:
            errores.append("Debes elegir al menos una acción a auditar")
        invalidas = [a for a in acciones if a not in ACCIONES_TABLA]
        if invalidas:
            errores.append(f"Acciones no permitidas sobre tablas: {', '.join(invalidas)}")
        try:
            objeto = (
                f"{normalizar_identificador(schema, 'el schema')}."
                f"{normalizar_identificador(tabla, 'la tabla')}"
            )
        except ValueError as error:
            errores.append(str(error))
            objeto = ""
        if not errores:
            partes = ", ".join(f"{a} ON {objeto}" for a in acciones)
            sentencia = f"CREATE AUDIT POLICY {nombre} ACTIONS {partes}"
    elif tipo == "sesion":
        acciones = acciones or list(ACCIONES_SESION)
        invalidas = [a for a in acciones if a not in ACCIONES_SESION]
        if invalidas:
            errores.append(f"Acciones no permitidas para sesiones: {', '.join(invalidas)}")
        if not errores:
            sentencia = f"CREATE AUDIT POLICY {nombre} ACTIONS {', '.join(acciones)}"
    else:
        errores.append("El tipo de política debe ser 'tabla' o 'sesion'")

    if errores:
        raise PoliticaInvalida(errores)
    return nombre, sentencia


def crear_politica(
    sentencia: Sentencia,
    nombre: str,
    tipo: str,
    acciones: list[str],
    schema: str = "",
    tabla: str = "",
    habilitar: bool = True,
) -> str:
    nombre, create = construir_politica(nombre, tipo, acciones, schema, tabla)
    sentencia(create)
    if habilitar:
        sentencia(f"AUDIT POLICY {nombre}")
    return nombre


def habilitar_politica(sentencia: Sentencia, nombre: str) -> str:
    nombre = normalizar_identificador(nombre, "la política")
    sentencia(f"AUDIT POLICY {nombre}")
    return nombre


def deshabilitar_politica(sentencia: Sentencia, nombre: str) -> str:
    nombre = normalizar_identificador(nombre, "la política")
    sentencia(f"NOAUDIT POLICY {nombre}")
    return nombre


def eliminar_politica(sentencia: Sentencia, nombre: str) -> str:
    nombre = normalizar_identificador(nombre, "la política")
    if nombre.startswith("ORA_"):
        raise PoliticaInvalida(["Las políticas predefinidas de Oracle (ORA_) no se eliminan"])
    sentencia(f"DROP AUDIT POLICY {nombre}")
    return nombre


def registros(
    consulta: Consulta, politica: str = "", usuario: str = "", limite: int = 100
) -> list[dict[str, Any]]:
    condiciones = []
    params: dict[str, Any] = {"limite": max(1, min(limite, 500))}
    if politica:
        condiciones.append("unified_audit_policies LIKE '%' || :politica || '%'")
        params["politica"] = politica.strip().upper()
    if usuario:
        condiciones.append("dbusername = :usuario")
        params["usuario"] = usuario.strip().upper()
    donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    sql = f"""
SELECT TO_CHAR(event_timestamp, 'DD/MM/YYYY HH24:MI:SS'), dbusername, action_name,
       object_schema, object_name, return_code, unified_audit_policies,
       DBMS_LOB.SUBSTR(sql_text, 300, 1)
FROM unified_audit_trail
{donde}
ORDER BY event_timestamp DESC
FETCH FIRST :limite ROWS ONLY
"""
    return [
        {
            "fecha": fecha,
            "usuario": usuario_bd,
            "accion": accion,
            "schema": schema,
            "objeto": objeto,
            "codigo_retorno": codigo,
            "politicas": politicas,
            "sql": texto,
        }
        for fecha, usuario_bd, accion, schema, objeto, codigo, politicas, texto in consulta(
            sql, params
        )
    ]
