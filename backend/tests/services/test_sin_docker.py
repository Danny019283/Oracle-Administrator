from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
PERMITIDOS = {"entorno_contenedor.py", "entorno_fabrica.py"}
PROHIBIDOS = ("docker", "podman", "contenedor=")


def _modulos():
    for carpeta in ("services", "api"):
        for modulo in (SRC / carpeta).rglob("*.py"):
            if modulo.name not in PERMITIDOS:
                yield modulo


def test_hay_modulos_que_revisar():
    assert any(m.name == "respaldos.py" for m in _modulos())


@pytest.mark.parametrize("modulo", list(_modulos()), ids=lambda m: str(m.relative_to(SRC)))
def test_ningun_modulo_menciona_docker_podman_ni_contenedor(modulo):
    texto = modulo.read_text(encoding="utf-8").lower()

    assert [p for p in PROHIBIDOS if p in texto] == []
