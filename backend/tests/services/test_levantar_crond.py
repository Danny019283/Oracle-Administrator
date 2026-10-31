"""RN-14: los scripts de arranque levantan crond en el contenedor cuando Oracle esta listo."""
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
SCRIPTS = ["levantar-oracle21c.sh", "levantar-oracle21c.bat"]
LISTO = "DATABASE IS READY TO USE"
FINAL = "Oracle listo en localhost:1521"


def _leer(nombre: str) -> str:
    return (RAIZ / nombre).read_bytes().decode("utf-8")


def _linea_crond(texto: str) -> str:
    lineas = [l for l in texto.splitlines() if "exec -u root oracle21c" in l]
    assert len(lineas) == 1
    return lineas[0]


@pytest.mark.parametrize("nombre", SCRIPTS)
def test_arranca_crond_como_root_de_forma_idempotente(nombre):
    linea = _linea_crond(_leer(nombre))
    # redireccion y || dentro de las comillas dobles
    assert 'sh -c "pgrep -x crond >/dev/null 2>&1 || crond"' in linea


@pytest.mark.parametrize("nombre", SCRIPTS)
def test_crond_va_despues_de_esperar_oracle_y_antes_del_mensaje_final(nombre):
    texto = _leer(nombre)
    assert texto.index(LISTO) < texto.index("exec -u root oracle21c") < texto.index(FINAL)


@pytest.mark.parametrize("nombre", SCRIPTS)
def test_fallo_de_crond_no_aborta_y_avisa(nombre):
    texto = _leer(nombre)
    assert "no se pudo arrancar crond" in texto
    if nombre.endswith(".sh"):
        assert "|| echo" in _linea_crond(texto)
    else:
        lineas = texto.splitlines()
        i = lineas.index(_linea_crond(texto))
        assert lineas[i + 1].strip().startswith("if errorlevel 1 echo")
        assert "exit" not in lineas[i + 1]


def test_finales_de_linea_se_conservan():
    assert b"\r" not in (RAIZ / "levantar-oracle21c.sh").read_bytes()
    bat = (RAIZ / "levantar-oracle21c.bat").read_bytes()
    assert bat.count(b"\r\n") in (0, bat.count(b"\n"))  # no mezcla CRLF y LF


def test_sh_sin_errores_de_sintaxis():
    if shutil.which("bash") is None:
        pytest.skip("bash no disponible")
    r = subprocess.run(["bash", "-n", str(RAIZ / "levantar-oracle21c.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
