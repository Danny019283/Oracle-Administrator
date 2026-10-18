import pytest

from src.services.login import SolicitudInvalida, SolicitudLogin, validar_login

DATOS = dict(
    host="localhost",
    puerto="1521",
    servicio="XEPDB1",
    usuario="HR",
    password="s3creta!",
)


def validar(**cambios):
    return validar_login(**{**DATOS, **cambios})


def errores_de(**cambios):
    with pytest.raises(SolicitudInvalida) as error:
        validar(**cambios)
    return error.value.errores


def test_una_solicitud_completa_es_valida():
    assert validar() == SolicitudLogin(
        host="localhost",
        puerto=1521,
        servicio="XEPDB1",
        usuario="HR",
        password="s3creta!",
        sysdba=False,
    )


def test_conserva_el_check_sysdba():
    assert validar(sysdba=True).sysdba is True


def test_acepta_el_puerto_como_numero():
    assert validar(puerto=1521).puerto == 1521


@pytest.mark.parametrize(
    "campo", ["host", "puerto", "servicio", "usuario", "password"]
)
@pytest.mark.parametrize("vacio", ["", "   "])
def test_un_campo_obligatorio_vacio_se_rechaza_nombrandolo(campo, vacio):
    errores = errores_de(**{campo: vacio})

    assert len(errores) == 1
    assert campo in errores[0]


def test_informa_todos_los_campos_vacios_a_la_vez():
    errores = errores_de(host="", servicio="", usuario="")

    assert len(errores) == 3


@pytest.mark.parametrize("puerto", ["abc", "15 21", "1521.5", "-1"])
def test_un_puerto_no_numerico_se_rechaza(puerto):
    errores = errores_de(puerto=puerto)

    assert len(errores) == 1
    assert "puerto" in errores[0]


@pytest.mark.parametrize("puerto", ["0", "65536", 0, 70000])
def test_un_puerto_fuera_de_rango_se_rechaza(puerto):
    errores = errores_de(puerto=puerto)

    assert len(errores) == 1
    assert "puerto" in errores[0]


@pytest.mark.parametrize("puerto", ["1", "65535"])
def test_los_limites_del_rango_son_validos(puerto):
    assert validar(puerto=puerto).puerto == int(puerto)


def test_recorta_los_espacios_de_host_servicio_y_usuario_pero_no_de_la_password():
    solicitud = validar(host=" localhost ", servicio=" XEPDB1 ", usuario=" HR ", password=" s3 ")

    assert (solicitud.host, solicitud.servicio, solicitud.usuario) == (
        "localhost",
        "XEPDB1",
        "HR",
    )
    assert solicitud.password == " s3 "


def test_el_mensaje_de_error_no_contiene_la_password():
    with pytest.raises(SolicitudInvalida) as error:
        validar(puerto="abc", password="s3creta!")

    assert "s3creta!" not in str(error.value)
