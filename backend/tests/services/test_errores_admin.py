from src.services.errores_admin import explicar_error_admin


def test_dpy_6005_no_menciona_el_contenedor():
    texto = explicar_error_admin("DPY-6005: cannot connect to database")

    assert "oracle21c" not in texto
    assert "contenedor" not in texto.lower()
    assert "servidor de Oracle" in texto


def test_ora_65096_conserva_el_contenedor_raiz():
    assert "contenedor raíz (CDB)" in explicar_error_admin("ORA-65096: invalid common user")
