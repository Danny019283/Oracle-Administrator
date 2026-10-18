from src.services.expdp_runner import Conexion
from src.services.sesiones import AlmacenSesiones

CONEXION = Conexion(usuario="USUARIO_PRUEBA", password="s3creta!", servicio="XEPDB1")
MINUTO = 60


class RelojFalso:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float):
        self.ahora += segundos


def _almacen():
    reloj = RelojFalso()
    return AlmacenSesiones(reloj=reloj), reloj


def test_una_sesion_sin_uso_durante_mas_de_15_minutos_deja_de_resolver():
    almacen, reloj = _almacen()
    token = almacen.crear(CONEXION)

    reloj.avanzar(15 * MINUTO + 1)

    assert almacen.resolver(token) is None


def test_una_sesion_con_menos_de_15_minutos_sin_uso_sigue_resolviendo():
    almacen, reloj = _almacen()
    token = almacen.crear(CONEXION)

    reloj.avanzar(15 * MINUTO)

    assert almacen.resolver(token) == CONEXION


def test_cada_resolucion_valida_renueva_el_plazo():
    almacen, reloj = _almacen()
    token = almacen.crear(CONEXION)

    for _ in range(4):
        reloj.avanzar(10 * MINUTO)
        assert almacen.resolver(token) == CONEXION


def test_el_plazo_se_cuenta_desde_el_ultimo_uso():
    almacen, reloj = _almacen()
    token = almacen.crear(CONEXION)
    reloj.avanzar(10 * MINUTO)
    almacen.resolver(token)

    reloj.avanzar(15 * MINUTO + 1)

    assert almacen.resolver(token) is None


def test_una_sesion_expirada_se_elimina_y_no_afecta_a_las_demas():
    almacen, reloj = _almacen()
    vieja = almacen.crear(CONEXION)
    reloj.avanzar(10 * MINUTO)
    reciente = almacen.crear(CONEXION)

    reloj.avanzar(6 * MINUTO)

    assert almacen.resolver(vieja) is None
    assert almacen.resolver(reciente) == CONEXION
