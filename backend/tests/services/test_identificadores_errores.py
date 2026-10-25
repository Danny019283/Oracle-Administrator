import pytest

from src.services.errores_admin import explicar_error_admin
from src.services.identificadores import (
    IdentificadorInvalido,
    normalizar_identificador,
    validar_password,
)


def test_normaliza_el_nombre_a_mayusculas():
    assert normalizar_identificador(" ventas_2026 ", "el usuario") == "VENTAS_2026"


@pytest.mark.parametrize("valor", ["", "1ABC", "HR; DROP USER X", "A B", 'X"Y', "a" * 129])
def test_rechaza_nombres_que_podrian_inyectar_sql(valor):
    with pytest.raises(IdentificadorInvalido):
        normalizar_identificador(valor, "el usuario")


def test_la_password_no_admite_comillas_dobles():
    with pytest.raises(IdentificadorInvalido, match="comillas"):
        validar_password('abc"; DROP USER HR CASCADE --')


def test_la_password_es_obligatoria():
    with pytest.raises(IdentificadorInvalido):
        validar_password("")


def test_explica_errores_de_privilegios():
    assert "privilegios" in explicar_error_admin("ORA-01031: privilegios insuficientes")


def test_explica_el_error_de_usuarios_comunes_en_el_cdb():
    assert "C##" in explicar_error_admin("ORA-65096: nombre de usuario o rol común no válido")


def test_reutiliza_las_explicaciones_de_respaldos():
    assert "contraseña" in explicar_error_admin("ORA-01017: invalid username/password")


def test_error_desconocido_da_explicacion_generica():
    assert "no está catalogado" in explicar_error_admin("ORA-99999: algo raro")
