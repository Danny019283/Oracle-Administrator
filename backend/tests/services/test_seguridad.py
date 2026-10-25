import pytest

from src.services import seguridad


class ConsultaFalsa:
    def __init__(self):
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        if "dba_users" in sql:
            return [("HR", "OPEN", "USERS", "TEMP", "DEFAULT", "01/10/2026")]
        if "dba_tablespaces" in sql:
            return [("USERS", "PERMANENT"), ("TEMP", "TEMPORARY")]
        if "dba_roles" in sql:
            return [("CONNECT",), ("RESOURCE",)]
        if "system_privilege_map" in sql:
            return [("CREATE SESSION",), ("CREATE TABLE",)]
        if "dba_role_privs" in sql:
            return [("CONNECT", "NO")]
        if "dba_sys_privs" in sql:
            return [("CREATE SESSION", "NO")]
        if "dba_ts_quotas" in sql:
            return [("USERS", 1.5, -1)]
        return []


class SentenciaFalsa:
    def __init__(self):
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)


def test_lista_solo_usuarios_no_mantenidos_por_oracle():
    consulta = ConsultaFalsa()

    usuarios = seguridad.listar_usuarios(consulta)

    assert usuarios[0]["usuario"] == "HR"
    assert "oracle_maintained = 'N'" in consulta.llamadas[0][0]


def test_detalle_incluye_roles_privilegios_y_cuotas():
    detalle = seguridad.detalle_usuario(ConsultaFalsa(), "hr")

    assert detalle["roles"] == [{"nombre": "CONNECT", "admin": False}]
    assert detalle["privilegios"] == [{"nombre": "CREATE SESSION", "admin": False}]
    assert detalle["cuotas"] == [{"tablespace": "USERS", "usado_mb": 1.5, "ilimitada": True}]


def test_crea_usuario_con_cuota_y_permiso_de_conexion():
    sentencia = SentenciaFalsa()

    nombre = seguridad.crear_usuario(
        ConsultaFalsa(), sentencia, "ventas", "Clave123", "users", "temp", "100m"
    )

    assert nombre == "VENTAS"
    assert sentencia.sqls == [
        'CREATE USER VENTAS IDENTIFIED BY "Clave123" DEFAULT TABLESPACE USERS '
        "TEMPORARY TABLESPACE TEMP QUOTA 100M ON USERS",
        "GRANT CREATE SESSION TO VENTAS",
    ]


def test_crear_usuario_reporta_todos_los_errores_y_no_ejecuta_nada():
    sentencia = SentenciaFalsa()

    with pytest.raises(seguridad.SolicitudInvalida) as error:
        seguridad.crear_usuario(ConsultaFalsa(), sentencia, "1x", "", "NOEXISTE", "", "mucho")

    assert len(error.value.errores) == 5
    assert sentencia.sqls == []


def test_no_permite_administrar_usuarios_internos_de_oracle():
    sentencia = SentenciaFalsa()

    with pytest.raises(seguridad.UsuarioNoAdministrable):
        seguridad.eliminar_usuario(ConsultaFalsa(), sentencia, "SYS")

    assert sentencia.sqls == []


def test_bloquear_desbloquear_password_y_eliminar():
    sentencia = SentenciaFalsa()
    consulta = ConsultaFalsa()

    seguridad.bloquear(consulta, sentencia, "hr", True)
    seguridad.bloquear(consulta, sentencia, "hr", False)
    seguridad.cambiar_password(consulta, sentencia, "hr", "Nueva1")
    seguridad.eliminar_usuario(consulta, sentencia, "hr")

    assert sentencia.sqls == [
        "ALTER USER HR ACCOUNT LOCK",
        "ALTER USER HR ACCOUNT UNLOCK",
        'ALTER USER HR IDENTIFIED BY "Nueva1"',
        "DROP USER HR CASCADE",
    ]


def test_otorga_y_revoca_roles_y_privilegios_del_catalogo():
    sentencia = SentenciaFalsa()
    consulta = ConsultaFalsa()

    seguridad.cambiar_rol(consulta, sentencia, "hr", "resource", True)
    seguridad.cambiar_rol(consulta, sentencia, "hr", "connect", False)
    seguridad.cambiar_privilegio(consulta, sentencia, "hr", "create   table", True)
    seguridad.cambiar_privilegio(consulta, sentencia, "hr", "create session", False)

    assert sentencia.sqls == [
        "GRANT RESOURCE TO HR",
        "REVOKE CONNECT FROM HR",
        "GRANT CREATE TABLE TO HR",
        "REVOKE CREATE SESSION FROM HR",
    ]


def test_rechaza_roles_que_no_existen():
    with pytest.raises(seguridad.SolicitudInvalida):
        seguridad.cambiar_rol(ConsultaFalsa(), SentenciaFalsa(), "hr", "DBA; DROP", True)
