from pathlib import Path

import pytest

from src.services.entorno_local import EntornoLocal, SistemaLinux
from src.services.entorno_oracle import (
    ArchivoEntorno,
    ArchivoNoLegible,
    HerramientaNoDisponible,
    OperacionEntornoFallida,
    Salida,
)


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


class EjecutorSecuencia:
    """Ejecutor falso: devuelve las salidas dadas en orden (o lanza si es una excepción) y anota los argumentos."""

    def __init__(self, *salidas):
        self.salidas = list(salidas)
        self.llamadas = []

    def __call__(self, args, entrada=None, variables=None):
        self.llamadas.append(args)
        salida = self.salidas.pop(0)
        if isinstance(salida, Exception):
            raise salida
        return salida


@pytest.mark.parametrize("texto_ps", ["oracle", "  oracle\n", "\n\n oracle \n"])
def test_dar_permisos_en_linux_da_acl_al_propietario_del_proceso_pmon(texto_ps, tmp_path):
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto=texto_ps), Salida(codigo=0, texto=""))

    SistemaLinux().dar_permisos_a_oracle(tmp_path, "ORCL", ejecutor)

    assert ejecutor.llamadas == [
        ["ps", "-C", "ora_pmon_ORCL", "-o", "user="],
        ["setfacl", "-m", "u:oracle:rwx", str(tmp_path)],
    ]


def test_dar_permisos_en_linux_con_ps_fallido_no_ejecuta_setfacl(tmp_path):
    ejecutor = EjecutorSecuencia(Salida(codigo=1, texto="boom"))

    with pytest.raises(OperacionEntornoFallida, match="ps -C ora_pmon_ORCL"):
        SistemaLinux().dar_permisos_a_oracle(tmp_path, "ORCL", ejecutor)

    assert len(ejecutor.llamadas) == 1


@pytest.mark.parametrize("texto_ps", ["", "  \n \n"])
def test_dar_permisos_en_linux_con_ps_sin_usuario_falla_con_mensaje_claro(texto_ps, tmp_path):
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto=texto_ps))

    with pytest.raises(OperacionEntornoFallida, match="ps -C ora_pmon_ORCL"):
        SistemaLinux().dar_permisos_a_oracle(tmp_path, "ORCL", ejecutor)

    assert len(ejecutor.llamadas) == 1


def test_dar_permisos_en_linux_con_setfacl_fallido_lanza_con_su_salida(tmp_path):
    ejecutor = EjecutorSecuencia(
        Salida(codigo=0, texto="oracle"), Salida(codigo=1, texto="Operation not supported")
    )

    with pytest.raises(OperacionEntornoFallida, match="setfacl.*Operation not supported"):
        SistemaLinux().dar_permisos_a_oracle(tmp_path, "ORCL", ejecutor)


def test_dar_permisos_en_linux_sin_setfacl_instalado_lanza_error_claro(tmp_path):
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto="oracle"), HerramientaNoDisponible("setfacl"))

    with pytest.raises(OperacionEntornoFallida, match="setfacl"):
        SistemaLinux().dar_permisos_a_oracle(tmp_path, "ORCL", ejecutor)


@pytest.mark.parametrize("usuario", ["ora cle", "ora;cle", "$(id)", "-m", "a\tb c"])
def test_dar_permisos_en_linux_con_usuario_raro_lanza_sin_ejecutar_setfacl(usuario, tmp_path):
    ejecutor = EjecutorSecuencia(Salida(codigo=0, texto=usuario))

    with pytest.raises(OperacionEntornoFallida, match="usuario"):
        SistemaLinux().dar_permisos_a_oracle(tmp_path, "ORCL", ejecutor)

    assert len(ejecutor.llamadas) == 1


def test_dar_permisos_a_oracle_delega_en_el_sistema_con_ruta_sid_y_su_ejecutor(tmp_path):
    llamadas = []

    class SistemaEspia(SistemaLinux):
        def dar_permisos_a_oracle(self, ruta, sid, ejecutar):
            llamadas.append((ruta, sid, ejecutar))

    def ejecutor(*args, **kwargs):
        pass

    EntornoLocal(SistemaEspia(), ejecutor).dar_permisos_a_oracle(tmp_path, "XE")

    assert llamadas == [(tmp_path, "XE", ejecutor)]


def test_listar_archivos_devuelve_solo_los_archivos_regulares_sin_entrar_en_subcarpetas(tmp_path):
    archivo = tmp_path / "a_20240101_101010.dmp"
    archivo.write_bytes(b"x" * 5)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "dentro.log").write_text("no")

    assert entorno().listar_archivos(tmp_path) == [ArchivoEntorno(archivo.name, 5, archivo.stat().st_mtime)]


def test_listar_archivos_de_una_carpeta_que_no_existe_lanza_operacion_entorno_fallida(tmp_path):
    with pytest.raises(OperacionEntornoFallida):
        entorno().listar_archivos(tmp_path / "no_existe")


def test_borrar_archivo_borra_el_archivo_local(tmp_path):
    archivo = tmp_path / "a.dmp"
    archivo.write_text("x")

    entorno().borrar_archivo(archivo)

    assert not archivo.exists()


def test_borrar_archivo_con_error_de_es_lanza_operacion_entorno_fallida(tmp_path):
    carpeta = tmp_path / "carpeta"
    carpeta.mkdir()

    with pytest.raises(OperacionEntornoFallida):
        entorno().borrar_archivo(carpeta)
