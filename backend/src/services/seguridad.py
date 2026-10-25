import re
from collections.abc import Callable, Sequence
from typing import Any

from src.services.identificadores import normalizar_identificador, validar_password
from src.services.oracle_ejecucion import Sentencia

Consulta = Callable[..., Sequence[Sequence[Any]]]

SQL_USUARIOS = """
SELECT username, account_status, default_tablespace, temporary_tablespace, profile,
       TO_CHAR(created, 'DD/MM/YYYY')
FROM dba_users
WHERE oracle_maintained = 'N'
ORDER BY username
"""

SQL_ROLES_USUARIO = """
SELECT granted_role, admin_option FROM dba_role_privs WHERE grantee = :usuario ORDER BY granted_role
"""

SQL_PRIVILEGIOS_USUARIO = """
SELECT privilege, admin_option FROM dba_sys_privs WHERE grantee = :usuario ORDER BY privilege
"""

SQL_CUOTAS_USUARIO = """
SELECT tablespace_name, ROUND(bytes / 1048576, 2), max_bytes
FROM dba_ts_quotas WHERE username = :usuario ORDER BY tablespace_name
"""

SQL_TABLESPACES = """
SELECT tablespace_name, contents FROM dba_tablespaces
WHERE status = 'ONLINE' AND contents IN ('PERMANENT', 'TEMPORARY')
ORDER BY tablespace_name
"""

SQL_ROLES = "SELECT role FROM dba_roles ORDER BY role"
SQL_PRIVILEGIOS = "SELECT name FROM system_privilege_map ORDER BY name"

_CUOTA = re.compile(r"UNLIMITED|\d{1,6}[KMG]", re.IGNORECASE)


class SolicitudInvalida(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


class UsuarioNoAdministrable(Exception):
    pass


def listar_usuarios(consulta: Consulta) -> list[dict[str, Any]]:
    return [
        {
            "usuario": usuario,
            "estado": estado,
            "tablespace": ts,
            "temporal": temporal,
            "perfil": perfil,
            "creado": creado,
        }
        for usuario, estado, ts, temporal, perfil, creado in consulta(SQL_USUARIOS)
    ]


def _usuario_administrable(consulta: Consulta, usuario: str) -> str:
    """Solo se administran usuarios creados por personas (no los de Oracle)."""
    nombre = normalizar_identificador(usuario, "el usuario")
    if nombre not in {u["usuario"] for u in listar_usuarios(consulta)}:
        raise UsuarioNoAdministrable(
            f"El usuario {nombre} no existe o es un usuario interno de Oracle"
        )
    return nombre


def detalle_usuario(consulta: Consulta, usuario: str) -> dict[str, Any]:
    nombre = _usuario_administrable(consulta, usuario)
    datos = next(u for u in listar_usuarios(consulta) if u["usuario"] == nombre)
    params = {"usuario": nombre}
    return {
        **datos,
        "roles": [
            {"nombre": r, "admin": a == "YES"} for r, a in consulta(SQL_ROLES_USUARIO, params)
        ],
        "privilegios": [
            {"nombre": p, "admin": a == "YES"}
            for p, a in consulta(SQL_PRIVILEGIOS_USUARIO, params)
        ],
        "cuotas": [
            {"tablespace": ts, "usado_mb": usado, "ilimitada": maximo == -1}
            for ts, usado, maximo in consulta(SQL_CUOTAS_USUARIO, params)
        ],
    }


def catalogos(consulta: Consulta) -> dict[str, list[str]]:
    tablespaces = consulta(SQL_TABLESPACES)
    return {
        "tablespaces": [n for n, c in tablespaces if c == "PERMANENT"],
        "temporales": [n for n, c in tablespaces if c == "TEMPORARY"],
        "roles": [fila[0] for fila in consulta(SQL_ROLES)],
        "privilegios": [fila[0] for fila in consulta(SQL_PRIVILEGIOS)],
    }


def crear_usuario(
    consulta: Consulta,
    sentencia: Sentencia,
    usuario: str,
    password: str,
    tablespace: str,
    temporal: str,
    cuota: str = "UNLIMITED",
    permitir_conexion: bool = True,
) -> str:
    errores = []
    nombre = ""
    try:
        nombre = normalizar_identificador(usuario, "el usuario")
    except ValueError as error:
        errores.append(str(error))
    try:
        validar_password(password)
    except ValueError as error:
        errores.append(str(error))

    disponibles = catalogos(consulta)
    tablespace = (tablespace or "").upper()
    temporal = (temporal or "").upper()
    if tablespace not in disponibles["tablespaces"]:
        errores.append("Debes elegir un tablespace por defecto válido")
    if temporal not in disponibles["temporales"]:
        errores.append("Debes elegir un tablespace temporal válido")
    cuota = (cuota or "UNLIMITED").strip().upper()
    if not _CUOTA.fullmatch(cuota):
        errores.append("La cuota debe ser UNLIMITED o un tamaño como 100M, 500K o 1G")
    if errores:
        raise SolicitudInvalida(errores)

    sentencia(
        f'CREATE USER {nombre} IDENTIFIED BY "{password}" '
        f"DEFAULT TABLESPACE {tablespace} TEMPORARY TABLESPACE {temporal} "
        f"QUOTA {cuota} ON {tablespace}"
    )
    if permitir_conexion:
        sentencia(f"GRANT CREATE SESSION TO {nombre}")
    return nombre


def cambiar_password(consulta: Consulta, sentencia: Sentencia, usuario: str, password: str) -> str:
    nombre = _usuario_administrable(consulta, usuario)
    validar_password(password)
    sentencia(f'ALTER USER {nombre} IDENTIFIED BY "{password}"')
    return nombre


def bloquear(consulta: Consulta, sentencia: Sentencia, usuario: str, bloquear: bool) -> str:
    nombre = _usuario_administrable(consulta, usuario)
    sentencia(f"ALTER USER {nombre} ACCOUNT {'LOCK' if bloquear else 'UNLOCK'}")
    return nombre


def eliminar_usuario(consulta: Consulta, sentencia: Sentencia, usuario: str) -> str:
    nombre = _usuario_administrable(consulta, usuario)
    sentencia(f"DROP USER {nombre} CASCADE")
    return nombre


def cambiar_rol(
    consulta: Consulta, sentencia: Sentencia, usuario: str, rol: str, otorgar: bool
) -> str:
    nombre = _usuario_administrable(consulta, usuario)
    rol = (rol or "").strip().upper()
    if rol not in catalogos(consulta)["roles"]:
        raise SolicitudInvalida([f"El rol {rol or '(vacío)'} no existe"])
    if otorgar:
        sentencia(f"GRANT {rol} TO {nombre}")
    else:
        sentencia(f"REVOKE {rol} FROM {nombre}")
    return nombre


def cambiar_privilegio(
    consulta: Consulta, sentencia: Sentencia, usuario: str, privilegio: str, otorgar: bool
) -> str:
    nombre = _usuario_administrable(consulta, usuario)
    privilegio = " ".join((privilegio or "").split()).upper()
    if privilegio not in catalogos(consulta)["privilegios"]:
        raise SolicitudInvalida([f"El privilegio {privilegio or '(vacío)'} no existe"])
    if otorgar:
        sentencia(f"GRANT {privilegio} TO {nombre}")
    else:
        sentencia(f"REVOKE {privilegio} FROM {nombre}")
    return nombre
