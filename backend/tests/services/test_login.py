import pytest

from src.services.expdp_runner import Conexion
from src.services.login import (
    LoginFallido,
    SolicitudLogin,
    conectar_oracle,
    iniciar_sesion,
)
from src.services.sesiones import AlmacenSesiones

PASSWORD = "s3creta!"


def solicitud(**cambios):
    datos = dict(
        host="db.local",
        puerto=1522,
        servicio="XEPDB1",
        usuario="HR",
        password=PASSWORD,
        sysdba=False,
    )
    return SolicitudLogin(**{**datos, **cambios})


class ConectorFalso:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.llamadas: list[SolicitudLogin] = []

    def __call__(self, pedido: SolicitudLogin) -> None:
        self.llamadas.append(pedido)
        if self.error:
            raise self.error


class AlmacenEspia(AlmacenSesiones):
    def __init__(self):
        super().__init__()
        self.creadas = 0

    def crear(self, conexion):
        self.creadas += 1
        return super().crear(conexion)


def test_con_credenciales_validas_crea_la_sesion_con_la_conexion_completa():
    almacen = AlmacenSesiones()
    conector = ConectorFalso()

    sesion = iniciar_sesion(solicitud(), almacen, conector)

    assert almacen.resolver(sesion.token) == Conexion(
        usuario="HR",
        password=PASSWORD,
        servicio="XEPDB1",
        host="db.local",
        puerto=1522,
        sysdba=False,
    )
    assert conector.llamadas == [solicitud()]


def test_la_respuesta_indica_usuario_y_modo_sin_la_password():
    sesion = iniciar_sesion(solicitud(sysdba=True), AlmacenSesiones(), ConectorFalso())

    assert (sesion.usuario, sesion.sysdba) == ("HR", True)
    assert PASSWORD not in repr(sesion)


def test_la_sesion_recuerda_el_modo_sysdba():
    almacen = AlmacenSesiones()

    sesion = iniciar_sesion(solicitud(sysdba=True), almacen, ConectorFalso())

    assert almacen.resolver(sesion.token).sysdba is True


class ConexionFalsa:
    def __init__(self):
        self.cerrada = False

    def close(self):
        self.cerrada = True


class DriverFalso:
    AUTH_MODE_DEFAULT = "default"
    AUTH_MODE_SYSDBA = "sysdba"

    def __init__(self):
        self.conexion = ConexionFalsa()
        self.argumentos = None

    def connect(self, **kwargs):
        self.argumentos = kwargs
        return self.conexion


def test_conecta_a_host_puerto_y_servicio_como_usuario_normal():
    driver = DriverFalso()

    conectar_oracle(solicitud(), driver)

    assert driver.argumentos == {
        "user": "HR",
        "password": PASSWORD,
        "dsn": "db.local:1522/XEPDB1",
        "mode": "default",
    }
    assert driver.conexion.cerrada


def test_conecta_con_modo_sysdba_solo_si_el_check_esta_marcado():
    driver = DriverFalso()

    conectar_oracle(solicitud(sysdba=True), driver)

    assert driver.argumentos["mode"] == "sysdba"


@pytest.mark.parametrize(
    "error, codigo, explicacion, inalcanzable",
    [
        (
            "ORA-01017: invalid username/password; logon denied",
            "ORA-01017",
            "Usuario o contraseña de Oracle incorrectos",
            False,
        ),
        (
            "ORA-12541: TNS:no listener",
            "ORA-12541",
            "No hay un listener de Oracle escuchando en ese host y puerto",
            True,
        ),
        (
            "ORA-12514: TNS:listener does not currently know of service requested",
            "ORA-12514",
            "El servicio de Oracle indicado no existe",
            True,
        ),
        (
            "ORA-01031: insufficient privileges",
            "ORA-01031",
            "El usuario no tiene el privilegio necesario (¿SYSDBA?)",
            False,
        ),
        (
            "ORA-28000: the account is locked",
            "ORA-28000",
            "La cuenta de Oracle está bloqueada",
            False,
        ),
        (
            "ORA-28001: the password has expired",
            "ORA-28001",
            "La contraseña de Oracle ha expirado",
            False,
        ),
        (
            "DPY-6005: cannot connect to database (CONNECTION_ID=abc)",
            "DPY-6005",
            "No se pudo alcanzar el servidor de Oracle en ese host y puerto",
            True,
        ),
    ],
)
def test_traduce_el_error_de_oracle_a_mensaje_claro_mas_codigo(
    error, codigo, explicacion, inalcanzable
):
    almacen = AlmacenEspia()
    conector = ConectorFalso(Exception(f"{error} (clave {PASSWORD})"))

    with pytest.raises(LoginFallido) as capturado:
        iniciar_sesion(solicitud(), almacen, conector)

    fallo = capturado.value
    assert fallo.codigo == codigo
    assert fallo.inalcanzable is inalcanzable
    assert explicacion in fallo.mensaje
    assert codigo in fallo.mensaje
    assert almacen.creadas == 0
    assert PASSWORD not in fallo.mensaje
    assert PASSWORD not in str(fallo)


def test_con_el_check_sysdba_y_ora_01017_el_mensaje_sugiere_revisar_el_privilegio():
    # Por red Oracle no distingue «sin privilegio SYSDBA» de credenciales inválidas.
    with pytest.raises(LoginFallido) as capturado:
        iniciar_sesion(
            solicitud(sysdba=True),
            AlmacenEspia(),
            ConectorFalso(Exception(f"ORA-01017: invalid username/password {PASSWORD}")),
        )

    fallo = capturado.value
    assert fallo.mensaje == (
        "Usuario o contraseña de Oracle incorrectos, "
        "o el usuario no tiene privilegio SYSDBA (ORA-01017)"
    )
    assert fallo.codigo == "ORA-01017"
    assert fallo.inalcanzable is False
    assert PASSWORD not in fallo.mensaje


def test_sin_el_check_sysdba_ora_01017_conserva_el_mensaje_de_credenciales():
    with pytest.raises(LoginFallido) as capturado:
        iniciar_sesion(
            solicitud(sysdba=False),
            AlmacenEspia(),
            ConectorFalso(Exception("ORA-01017: invalid username/password")),
        )

    assert capturado.value.mensaje == "Usuario o contraseña de Oracle incorrectos (ORA-01017)"


def test_sys_sin_el_check_sysdba_pide_marcar_la_casilla():
    almacen = AlmacenEspia()

    with pytest.raises(LoginFallido) as capturado:
        iniciar_sesion(
            solicitud(usuario="SYS", sysdba=False),
            almacen,
            ConectorFalso(Exception("ORA-28009: connection as SYS should be as SYSDBA or SYSOPER")),
        )

    fallo = capturado.value
    assert fallo.mensaje == (
        "SYS debe conectarse como SYSDBA: marca la casilla «Iniciar como SYSDBA» (ORA-28009)"
    )
    assert fallo.codigo == "ORA-28009"
    assert fallo.inalcanzable is False
    assert almacen.creadas == 0


def test_un_error_de_oracle_no_catalogado_conserva_su_codigo():
    with pytest.raises(LoginFallido) as capturado:
        iniciar_sesion(
            solicitud(), AlmacenEspia(), ConectorFalso(Exception("ORA-00600: interno"))
        )

    assert capturado.value.codigo == "ORA-00600"
    assert "ORA-00600" in capturado.value.mensaje
    assert capturado.value.inalcanzable is False


def test_un_error_sin_codigo_da_un_mensaje_generico_sin_exponer_el_detalle():
    almacen = AlmacenEspia()

    with pytest.raises(LoginFallido) as capturado:
        iniciar_sesion(
            solicitud(), almacen, ConectorFalso(Exception(f"boom {PASSWORD}"))
        )

    assert capturado.value.codigo is None
    assert PASSWORD not in capturado.value.mensaje
    assert almacen.creadas == 0
