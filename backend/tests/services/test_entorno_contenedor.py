import re

import pytest

from src.services.entorno_contenedor import EntornoContenedor
from src.services.entorno_oracle import (
    ArchivoEntorno,
    ArchivoNoLegible,
    ComandoHerramienta,
    HerramientaNoDisponible,
    OperacionEntornoFallida,
    Salida,
)


class ProcesoFalso:
    def __init__(self, codigo_herramienta=0, falla=False):
        self.codigo_herramienta = codigo_herramienta
        self.falla = falla
        self.llamadas = []

    def __call__(self, args, entrada=None):
        self.llamadas.append((args, entrada))
        if "rman" in args and "cat" not in args:
            if self.falla:
                raise RuntimeError("docker no responde")
            return Salida(codigo=self.codigo_herramienta, texto="salida de la herramienta")
        return Salida(codigo=0, texto="contenido del archivo")


def ejecutar(proceso, script="linea1\nlinea2\n", **opciones):
    entorno = EntornoContenedor("oracle-test", proceso)
    return entorno.ejecutar(
        ComandoHerramienta(
            "rman", lambda ruta: ["target", "/", f"cmdfile={ruta}"], script, prefijo="rman", extension=".rman", **opciones
        )
    )


def test_escribe_el_script_por_stdin_con_umask_restrictivo_y_fuera_de_los_argumentos():
    proceso = ProcesoFalso()

    ejecutar(proceso, "linea1\nlinea2\n")

    args, entrada = proceso.llamadas[0]
    assert args[:5] == ["docker", "exec", "-i", "oracle-test", "sh"]
    assert args[-1].startswith("umask 077; cat > /tmp/rman_")
    assert entrada == "linea1\nlinea2\n"
    assert all("linea1" not in argumento for args, _ in proceso.llamadas for argumento in args)


def test_el_temporal_tiene_la_forma_prefijo_uuid_extension():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    assert re.fullmatch(r"umask 077; cat > /tmp/rman_[0-9a-f]{32}\.rman", proceso.llamadas[0][0][-1])


def test_la_herramienta_recibe_la_ruta_del_temporal():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[1][0] == ["docker", "exec", "oracle-test", "rman", "target", "/", f"cmdfile={ruta}"]


def test_con_variables_la_herramienta_se_ejecuta_con_env():
    proceso = ProcesoFalso()

    ejecutar(proceso, variables={"ORACLE_SID": "XE"})

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[1][0] == [
        "docker", "exec", "oracle-test", "env", "ORACLE_SID=XE", "rman", "target", "/", f"cmdfile={ruta}",
    ]


def test_devuelve_la_salida_de_la_herramienta():
    salida = ejecutar(ProcesoFalso(codigo_herramienta=7))

    assert salida == Salida(codigo=7, texto="salida de la herramienta")


def test_borra_el_temporal_con_rm_f_al_terminar():
    proceso = ProcesoFalso()

    ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_borra_el_temporal_aunque_la_herramienta_lance_una_excepcion():
    proceso = ProcesoFalso(falla=True)

    with pytest.raises(RuntimeError):
        ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_codigo_127_de_la_herramienta_lanza_herramienta_no_disponible_y_borra_el_temporal():
    proceso = ProcesoFalso(codigo_herramienta=127)

    with pytest.raises(HerramientaNoDisponible, match="rman"):
        ejecutar(proceso)

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert proceso.llamadas[-1][0] == ["docker", "exec", "oracle-test", "rm", "-f", ruta]


def test_si_falla_al_escribir_el_temporal_no_intenta_borrar_nada():
    llamadas = []

    def proceso(args, entrada=None):
        llamadas.append(args)
        raise HerramientaNoDisponible("docker")

    with pytest.raises(HerramientaNoDisponible, match="docker"):
        ejecutar(proceso)

    assert len(llamadas) == 1


def test_leer_archivo_ejecuta_cat_dentro_del_contenedor():
    proceso = ProcesoFalso()

    texto = EntornoContenedor("oracle-test", proceso).leer_archivo(EntornoContenedor.tipo_ruta("/u01/log.log"))

    assert proceso.llamadas == [(["docker", "exec", "oracle-test", "cat", "/u01/log.log"], None)]
    assert texto == "contenido del archivo"


def test_leer_archivo_con_cat_distinto_de_cero_lanza_archivo_no_legible():
    def proceso(args, entrada=None):
        return Salida(codigo=1, texto="cat: /u01/log.log: No such file or directory")

    with pytest.raises(ArchivoNoLegible):
        EntornoContenedor("oracle-test", proceso).leer_archivo(EntornoContenedor.tipo_ruta("/u01/log.log"))


def test_con_cli_podman_emite_podman_exec_con_la_misma_forma_que_docker():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso, cli="podman").ejecutar(
        ComandoHerramienta("rman", lambda ruta: ["cmdfile=" + ruta], "x", prefijo="rman", variables={"ORACLE_SID": "XE"})
    )

    ruta = proceso.llamadas[0][0][-1].split("cat > ")[1]
    assert [args for args, _ in proceso.llamadas] == [
        ["podman", "exec", "-i", "oracle-test", "sh", "-c", f"umask 077; cat > {ruta}"],
        ["podman", "exec", "oracle-test", "env", "ORACLE_SID=XE", "rman", f"cmdfile={ruta}"],
        ["podman", "exec", "oracle-test", "rm", "-f", ruta],
    ]


def test_con_cli_podman_leer_archivo_emite_podman_exec_cat():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso, cli="podman").leer_archivo(EntornoContenedor.tipo_ruta("/u01/log.log"))

    assert proceso.llamadas == [(["podman", "exec", "oracle-test", "cat", "/u01/log.log"], None)]


def test_crear_carpeta_ejecuta_mkdir_p_dentro_del_contenedor():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso).crear_carpeta(EntornoContenedor.tipo_ruta("/u01/respaldos/diario"))

    assert proceso.llamadas == [(["docker", "exec", "oracle-test", "mkdir", "-p", "/u01/respaldos/diario"], None)]


def test_crear_carpeta_con_cli_podman_emite_podman_exec_mkdir_p():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso, cli="podman").crear_carpeta(EntornoContenedor.tipo_ruta("/u01/r"))

    assert proceso.llamadas == [(["podman", "exec", "oracle-test", "mkdir", "-p", "/u01/r"], None)]


def test_crear_carpeta_con_codigo_distinto_de_cero_lanza_operacion_entorno_fallida_con_la_salida():
    def proceso(args, entrada=None):
        return Salida(codigo=1, texto="mkdir: permission denied")

    with pytest.raises(OperacionEntornoFallida, match="mkdir: permission denied"):
        EntornoContenedor("oracle-test", proceso).crear_carpeta(EntornoContenedor.tipo_ruta("/root/x"))


def test_dar_permisos_a_oracle_ejecuta_chown_y_chmod_como_root_en_orden():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso).dar_permisos_a_oracle(EntornoContenedor.tipo_ruta("/u01/respaldos"), "XE")

    assert proceso.llamadas == [
        (["docker", "exec", "-u", "root", "oracle-test", "chown", "oracle:oinstall", "/u01/respaldos"], None),
        (["docker", "exec", "-u", "root", "oracle-test", "chmod", "u+rwx", "/u01/respaldos"], None),
    ]


def test_dar_permisos_a_oracle_ignora_el_sid():
    con_xe, con_orcl = ProcesoFalso(), ProcesoFalso()

    EntornoContenedor("oracle-test", con_xe).dar_permisos_a_oracle(EntornoContenedor.tipo_ruta("/u01/r"), "XE")
    EntornoContenedor("oracle-test", con_orcl).dar_permisos_a_oracle(EntornoContenedor.tipo_ruta("/u01/r"), "ORCL")

    assert con_xe.llamadas == con_orcl.llamadas


def test_dar_permisos_a_oracle_con_podman_y_usuario_propio():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso, cli="podman", usuario_oracle="grid:asmadmin").dar_permisos_a_oracle(
        EntornoContenedor.tipo_ruta("/u01/r"), "XE"
    )

    assert proceso.llamadas[0][0] == ["podman", "exec", "-u", "root", "oracle-test", "chown", "grid:asmadmin", "/u01/r"]


def test_dar_permisos_a_oracle_nunca_crea_la_carpeta():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso).dar_permisos_a_oracle(EntornoContenedor.tipo_ruta("/u01/r"), "XE")

    assert all("mkdir" not in args for args, _ in proceso.llamadas)


def test_dar_permisos_a_oracle_si_chown_falla_lanza_con_la_salida_y_no_ejecuta_chmod():
    llamadas = []

    def proceso(args, entrada=None):
        llamadas.append(args)
        return Salida(codigo=1, texto="chown: No such file or directory")

    with pytest.raises(OperacionEntornoFallida, match="No such file or directory"):
        EntornoContenedor("oracle-test", proceso).dar_permisos_a_oracle(EntornoContenedor.tipo_ruta("/no/existe"), "XE")

    assert len(llamadas) == 1


def test_dar_permisos_a_oracle_si_chmod_falla_lanza_con_la_salida():
    def proceso(args, entrada=None):
        return Salida(codigo=1 if "chmod" in args else 0, texto="chmod: Operation not permitted")

    with pytest.raises(OperacionEntornoFallida, match="Operation not permitted"):
        EntornoContenedor("oracle-test", proceso).dar_permisos_a_oracle(EntornoContenedor.tipo_ruta("/u01/r"), "XE")


def test_listar_archivos_ejecuta_find_y_devuelve_los_archivos_del_directorio():
    llamadas = []

    def proceso(args, entrada=None):
        llamadas.append(args)
        return Salida(codigo=0, texto="a_20240101_101010.dmp\t1024\t1704103810.5\nb.log\t10\t1704103811.0\n")

    archivos = EntornoContenedor("oracle-test", proceso).listar_archivos(EntornoContenedor.tipo_ruta("/u01/dump"))

    assert llamadas == [
        [
            "docker", "exec", "oracle-test", "find", "/u01/dump", "-maxdepth", "1", "-type", "f",
            "-printf", r"%f\t%s\t%T@\n",  # find interpreta las secuencias de escape
        ]
    ]  # fmt: skip
    assert archivos == [
        ArchivoEntorno("a_20240101_101010.dmp", 1024, 1704103810.5),
        ArchivoEntorno("b.log", 10, 1704103811.0),
    ]


def test_listar_archivos_de_una_carpeta_vacia_devuelve_lista_vacia():
    entorno = EntornoContenedor("c", lambda args, entrada=None: Salida(0, ""))

    assert entorno.listar_archivos(EntornoContenedor.tipo_ruta("/u01")) == []


def test_listar_archivos_con_find_fallido_lanza_operacion_entorno_fallida_con_la_salida():
    def proceso(args, entrada=None):
        return Salida(codigo=1, texto="find: '/u01/x': No such file or directory")

    with pytest.raises(OperacionEntornoFallida, match="No such file"):
        EntornoContenedor("c", proceso).listar_archivos(EntornoContenedor.tipo_ruta("/u01/x"))


def test_borrar_archivo_ejecuta_rm_f_dentro_del_contenedor():
    proceso = ProcesoFalso()

    EntornoContenedor("oracle-test", proceso, cli="podman").borrar_archivo(EntornoContenedor.tipo_ruta("/u01/a.dmp"))

    assert proceso.llamadas == [(["podman", "exec", "oracle-test", "rm", "-f", "/u01/a.dmp"], None)]


def test_borrar_archivo_con_rm_fallido_lanza_operacion_entorno_fallida_con_la_salida():
    def proceso(args, entrada=None):
        return Salida(codigo=1, texto="rm: cannot remove: Permission denied")

    with pytest.raises(OperacionEntornoFallida, match="Permission denied"):
        EntornoContenedor("c", proceso).borrar_archivo(EntornoContenedor.tipo_ruta("/u01/a.dmp"))
