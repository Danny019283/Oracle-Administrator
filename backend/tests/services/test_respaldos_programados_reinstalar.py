import dataclasses
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services import respaldos_programados as rp
from src.services.entorno_oracle import ArchivoEntorno, HerramientaNoDisponible
from src.services.politica_respaldo import Programacion, envoltorio, script_rman
from tests.services.entorno_falso import EntornoFalso

P = PurePosixPath
CARPETA = P("/resp/scripts_programados")
HOME = "/u01/app/oracle/product/21c/dbhome_1"


class EntornoWindows(EntornoFalso):
    tipo_ruta = PureWindowsPath


class Programador:
    def __init__(self, fallos=None):
        self.fallos = fallos or {}
        self.llamadas = []

    def instalar(self, id_programacion, prog, ruta_script):
        self.llamadas.append((id_programacion, prog, ruta_script))
        if id_programacion in self.fallos:
            raise self.fallos[id_programacion]


class Consulta:
    def __init__(self, filas):
        self.filas = filas
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        return self.filas


def fila(id=1, nombre="diario", politica="FULL", frecuencia="DIARIO", hora="02:30", dia=None,
         intervalo=None, carpeta="/resp/scripts_programados", ext=".sh"):
    sep = "\\" if ext == ".bat" else "/"
    base = f"{carpeta}{sep}{nombre}"
    return (id, nombre, politica, frecuencia, hora, dia, intervalo, "DIR_RESP", base + ext,
            base + ".rman", "local", f"OracleAdmin_{id}", None, None, None)


def archivos(*nombres):
    return [ArchivoEntorno(n, 1, 1.0) for n in nombres]


def entorno_con(carpetas=None, clase=EntornoFalso, **kwargs):
    kwargs.setdefault("variables_entorno", {"ORACLE_HOME": HOME})
    return clase(archivos=carpetas or {}, **kwargs)


def esperados(nombre, politica="FULL", destino=P("/resp")):
    rman = script_rman(politica, destino)
    sh = envoltorio(nombre, "ORCL", HOME, destino / "scripts_programados" / f"{nombre}.rman", destino)
    return rman, sh


def test_con_los_scripts_presentes_solo_instala_la_tarea():
    entorno = entorno_con({CARPETA: archivos("diario.rman", "diario.sh")})
    programador, consulta = Programador(), Consulta([fila()])

    resultado = rp.reinstalar(consulta, entorno, programador, "ORCL")

    assert resultado == rp.ResultadoReinstalacion(reinstaladas=1, fallidas=())
    assert entorno.escrituras == []
    assert programador.llamadas == [
        (1, Programacion("diario", "DIR_RESP", "FULL", "DIARIO", "02:30"), "/resp/scripts_programados/diario.sh")
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        resultado.reinstaladas = 5


def test_regenera_solo_el_rman_faltante_con_el_contenido_de_crear():
    entorno = entorno_con({CARPETA: archivos("diario.sh")})

    rp.reinstalar(Consulta([fila()]), entorno, Programador(), "ORCL")

    rman, _ = esperados("diario")
    assert entorno.escrituras == [(CARPETA / "diario.rman", rman, False)]


def test_regenera_solo_el_envoltorio_faltante_ejecutable():
    entorno = entorno_con({CARPETA: archivos("diario.rman")})

    rp.reinstalar(Consulta([fila()]), entorno, Programador(), "ORCL")

    _, sh = esperados("diario")
    assert entorno.escrituras == [(CARPETA / "diario.sh", sh, True)]
    assert "ORACLE_SID=ORCL" in sh
    assert entorno.consultas_entorno == ["ORACLE_HOME"]


def test_carpeta_perdida_regenera_ambos_y_reinstala():
    entorno = entorno_con(fallo_listado="no existe la carpeta")
    programador = Programador()

    resultado = rp.reinstalar(Consulta([fila(politica="INCREMENTAL")]), entorno, programador, "ORCL")

    rman, sh = esperados("diario", "INCREMENTAL")
    assert entorno.escrituras == [(CARPETA / "diario.rman", rman, False), (CARPETA / "diario.sh", sh, True)]
    assert resultado.reinstaladas == 1 and len(programador.llamadas) == 1


def test_fallo_del_programador_no_aborta_y_se_informa():
    filas = [
        fila(1, "a"),
        fila(2, "b"),
        fila(3, "c", carpeta="/otro/scripts_programados"),
        fila(4, "d"),
    ]
    entorno = entorno_con({CARPETA: archivos("a.rman", "a.sh", "b.rman", "b.sh", "d.rman", "d.sh"),
                           P("/otro/scripts_programados"): archivos("c.rman", "c.sh")})
    error = HerramientaNoDisponible("crontab")
    programador = Programador({2: error})

    resultado = rp.reinstalar(Consulta(filas), entorno, programador, "ORCL")

    assert [c[0] for c in programador.llamadas] == [1, 2, 3, 4]
    assert resultado.reinstaladas == 3
    assert resultado.fallidas == (rp.FalloReinstalacion("b", str(error)),)


def test_oracle_home_ausente_y_fallo_de_escritura_se_anotan_y_siguen_las_demas():
    filas = [fila(1, "a"), fila(2, "b"), fila(3, "c")]
    carpetas = {CARPETA: archivos("a.rman", "a.sh", "c.rman", "c.sh")}

    # b no tiene scripts: hay que escribir, pero ORACLE_HOME no está
    entorno = entorno_con(carpetas, variables_entorno={})
    programador = Programador()
    resultado = rp.reinstalar(Consulta(filas), entorno, programador, "ORCL")
    assert [c[0] for c in programador.llamadas] == [1, 3]
    assert resultado.reinstaladas == 2
    assert [f.nombre for f in resultado.fallidas] == ["b"]
    assert "ORACLE_HOME" in resultado.fallidas[0].mensaje
    assert entorno.escrituras == []

    # ahora la escritura falla
    entorno = entorno_con(carpetas, fallo_escritura="disco lleno")
    programador = Programador()
    resultado = rp.reinstalar(Consulta(filas), entorno, programador, "ORCL")
    assert resultado.reinstaladas == 2
    assert resultado.fallidas == (rp.FalloReinstalacion("b", "disco lleno"),)


def test_oracle_home_no_valido_es_un_fallo_de_esa_fila():
    entorno = entorno_con({}, variables_entorno={"ORACLE_HOME": "relativo; rm"})
    programador = Programador()

    resultado = rp.reinstalar(Consulta([fila()]), entorno, programador, "ORCL")

    assert resultado.reinstaladas == 0 and programador.llamadas == []
    assert resultado.fallidas[0].nombre == "diario" and resultado.fallidas[0].mensaje


def test_reinstalar_dos_veces_repite_las_mismas_llamadas():
    entorno = entorno_con({CARPETA: archivos("diario.rman", "diario.sh", "semana.rman", "semana.sh")})
    programador = Programador()
    consulta = Consulta([fila(), fila(2, "semana", "FULL", "SEMANAL", "03:00", 3)])

    rp.reinstalar(consulta, entorno, programador, "ORCL")
    primera = list(programador.llamadas)
    rp.reinstalar(consulta, entorno, programador, "ORCL")

    assert programador.llamadas == primera + primera
    assert primera[1][1] == Programacion("semana", "DIR_RESP", "FULL", "SEMANAL", "03:00", 3)


def test_horas_conserva_el_intervalo_y_sin_dia_ni_intervalo_usa_los_valores_por_defecto():
    entorno = entorno_con({CARPETA: archivos("h.rman", "h.sh", "m.rman", "m.sh")})
    programador = Programador()
    filas = [fila(1, "h", "TRANSACCIONAL", "HORAS", None, None, 6), fila(2, "m", "FULL", "MENSUAL", "01:00")]

    rp.reinstalar(Consulta(filas), entorno, programador, "ORCL")

    assert programador.llamadas[0][1] == Programacion("h", "DIR_RESP", "TRANSACCIONAL", "HORAS", None, None, 6)
    assert programador.llamadas[1][1].dia is None and programador.llamadas[1][1].intervalo_horas == 2


def test_tabla_vacia_o_inexistente_no_hace_nada():
    entorno = entorno_con()
    programador = Programador()

    assert rp.reinstalar(Consulta([]), entorno, programador, "ORCL") == rp.ResultadoReinstalacion(0, ())
    assert programador.llamadas == [] and entorno.escrituras == [] and entorno.listados == []


def test_variante_windows_regenera_el_bat():
    carpeta = PureWindowsPath(r"C:\resp\scripts_programados")
    entorno = entorno_con(
        {carpeta: archivos("diario.rman")}, clase=EntornoWindows,
        variables_entorno={"ORACLE_HOME": r"C:\oracle\dbhome_1"},
    )
    programador = Programador()

    resultado = rp.reinstalar(Consulta([fila(carpeta=r"C:\resp\scripts_programados", ext=".bat")]),
                              entorno, programador, "ORCL")

    destino = PureWindowsPath(r"C:\resp")
    bat = envoltorio("diario", "ORCL", r"C:\oracle\dbhome_1", carpeta / "diario.rman", destino)
    assert entorno.escrituras == [(carpeta / "diario.bat", bat, True)]
    assert programador.llamadas[0][2] == r"C:\resp\scripts_programados\diario.bat"
    assert resultado.reinstaladas == 1


def test_no_ejecuta_sentencias_ni_borra_nada():
    consulta = Consulta([fila()])
    entorno = entorno_con({CARPETA: archivos("diario.sh")})

    rp.reinstalar(consulta, entorno, Programador(), "ORCL")

    assert len(consulta.llamadas) == 1 and consulta.llamadas[0][0].lstrip().upper().startswith("SELECT")
    assert entorno.borrados == []
