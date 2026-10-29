from pathlib import Path

import pytest

from src.services.entorno_local import EntornoLocal, SistemaLinux, SistemaWindows
from src.services.entorno_oracle import ArchivoNoLegible


def entorno():
    return EntornoLocal(SistemaLinux())


def test_las_rutas_del_entorno_local_son_path():
    assert entorno().tipo_ruta is Path


def test_leer_archivo_devuelve_el_contenido_del_archivo_local(tmp_path):
    archivo = tmp_path / "expdp.log"
    archivo.write_text("export terminado\n")

    assert entorno().leer_archivo(archivo) == "export terminado\n"


def test_leer_archivo_con_bytes_invalidos_los_reemplaza(tmp_path):
    archivo = tmp_path / "expdp.log"
    archivo.write_bytes(b"a\xffb")

    assert entorno().leer_archivo(archivo) == "a�b"


def test_leer_archivo_con_error_de_es_lanza_archivo_no_legible(tmp_path):
    with pytest.raises(ArchivoNoLegible):
        entorno().leer_archivo(tmp_path / "no_existe.log")


def test_crear_carpeta_crea_los_padres(tmp_path):
    carpeta = entorno().tipo_ruta(tmp_path) / "a" / "b"

    entorno().crear_carpeta(carpeta)

    assert carpeta.is_dir()


def test_crear_carpeta_no_falla_si_ya_existe(tmp_path):
    entorno().crear_carpeta(tmp_path)

    assert tmp_path.is_dir()


@pytest.mark.parametrize("sistema", [SistemaLinux(), SistemaWindows()])
def test_dar_permisos_a_oracle_con_sistema_sin_comportamiento_todavia_no_hace_nada(sistema, tmp_path):
    llamadas = []
    entorno_local = EntornoLocal(sistema, ejecutar=lambda *args, **kwargs: llamadas.append(args))

    assert entorno_local.dar_permisos_a_oracle(entorno_local.tipo_ruta(tmp_path), "XE") is None

    assert llamadas == []


def test_dar_permisos_a_oracle_delega_en_el_sistema_con_ruta_sid_y_su_ejecutor(tmp_path):
    llamadas = []

    class SistemaEspia(SistemaLinux):
        def dar_permisos_a_oracle(self, ruta, sid, ejecutar):
            llamadas.append((ruta, sid, ejecutar))

    def ejecutor(*args, **kwargs):
        pass

    EntornoLocal(SistemaEspia(), ejecutor).dar_permisos_a_oracle(tmp_path, "XE")

    assert llamadas == [(tmp_path, "XE", ejecutor)]
