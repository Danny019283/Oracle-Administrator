from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones

CONEXION = Conexion(usuario="USUARIO_PRUEBA", password="s3creta!", servicio="XEPDB1")


def test_crear_devuelve_un_token_que_resuelve_la_conexion():
    almacen = AlmacenSesiones()

    token = almacen.crear(CONEXION)

    assert almacen.resolver(token) == CONEXION


def test_los_tokens_son_opacos_largos_y_distintos_en_cada_llamada():
    almacen = AlmacenSesiones()

    tokens = {almacen.crear(CONEXION) for _ in range(50)}

    assert len(tokens) == 50
    assert all(len(token) >= 32 for token in tokens)
    assert all("s3creta" not in token and "USUARIO_PRUEBA" not in token for token in tokens)


def test_cerrar_elimina_la_sesion():
    almacen = AlmacenSesiones()
    token = almacen.crear(CONEXION)

    almacen.cerrar(token)

    assert almacen.resolver(token) is None


def test_cerrar_un_token_desconocido_no_falla():
    AlmacenSesiones().cerrar("inexistente")


def test_un_token_desconocido_no_resuelve():
    almacen = AlmacenSesiones()
    almacen.crear(CONEXION)

    assert almacen.resolver("inexistente") is None


def test_cerrar_una_sesion_no_afecta_a_las_demas():
    almacen = AlmacenSesiones()
    primero = almacen.crear(CONEXION)
    segundo = almacen.crear(CONEXION)

    almacen.cerrar(primero)

    assert almacen.resolver(segundo) == CONEXION
