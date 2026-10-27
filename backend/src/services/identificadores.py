import re

# Nombres simples de Oracle: empiezan con letra; letras, números, _, $ y #.
_IDENTIFICADOR = re.compile(r"[A-Za-z][A-Za-z0-9_$#]{0,127}")


class IdentificadorInvalido(ValueError):
    pass


def normalizar_identificador(valor: str, que: str) -> str:
    """Devuelve el nombre en mayúsculas o lanza IdentificadorInvalido.

    Las sentencias DDL no aceptan variables enlazadas, así que todo nombre que
    se concatena en una sentencia pasa antes por aquí.
    """
    valor = (valor or "").strip()
    if not valor:
        raise IdentificadorInvalido(f"Debes ingresar el nombre de {que}")
    if not _IDENTIFICADOR.fullmatch(valor):
        raise IdentificadorInvalido(
            f"El nombre de {que} debe empezar con una letra y usar solo letras, "
            "números, '_', '$' o '#' (máximo 128 caracteres)"
        )
    return valor.upper()


def validar_password(password: str) -> str:
    if not password:
        raise IdentificadorInvalido("Debes ingresar una contraseña")
    if '"' in password:
        raise IdentificadorInvalido("La contraseña no puede contener comillas dobles (\")")
    if len(password) > 1024:
        raise IdentificadorInvalido("La contraseña es demasiado larga")
    return password
