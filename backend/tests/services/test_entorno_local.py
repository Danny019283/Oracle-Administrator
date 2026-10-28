from pathlib import Path

from src.services.entorno_local import EntornoLocal, SistemaLinux


def entorno():
    return EntornoLocal(SistemaLinux())


def test_las_rutas_del_entorno_local_son_path():
    assert entorno().tipo_ruta is Path


def test_leer_archivo_devuelve_el_contenido_del_archivo_local(tmp_path):
    archivo = tmp_path / "expdp.log"
    archivo.write_text("export terminado\n")

    assert entorno().leer_archivo(archivo) == "export terminado\n"


def test_crear_carpeta_crea_los_padres(tmp_path):
    carpeta = entorno().tipo_ruta(tmp_path) / "a" / "b"

    entorno().crear_carpeta(carpeta)

    assert carpeta.is_dir()


def test_crear_carpeta_no_falla_si_ya_existe(tmp_path):
    entorno().crear_carpeta(tmp_path)

    assert tmp_path.is_dir()
