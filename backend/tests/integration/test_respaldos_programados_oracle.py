import os
import secrets
import subprocess
import sys
import time
from types import SimpleNamespace

import oracledb
import pytest

from src.services import respaldos_programados as servicio
from src.services.archivos_respaldo import eliminar_respaldo, listar_respaldos
from src.services.directorios import Directorio
from src.services.entorno_fabrica import fabrica_desde_variables, programador_desde_variables
from src.services.expdp_runner import Conexion
from src.services.instancia import sid_de_instancia
from src.services.oracle_conexion import consulta_oracle
from src.services.oracle_ejecucion import sentencia_oracle
from src.services.politica_respaldo import Programacion
from src.services.programador_tareas import marca_cron
from src.services.respaldo_full import en_archivelog
from tests.integration.conftest import (
    CONTENEDOR,
    HOST,
    PUERTO,
    SERVICIO,
    _ejecutar_ignorando_errores,
    _password_admin,
    docker,
)

pytestmark = pytest.mark.integration

CLI = os.environ.get("ORACLE_CONTAINER_CLI", "docker")


@pytest.fixture
def contexto():
    """Servicios reales sobre el contenedor y un DIRECTORY de prueba; se borra al terminar."""
    password = _password_admin()
    if password is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para preparar la base de pruebas")
    conexion = Conexion("SYS", password, SERVICIO, HOST, int(PUERTO), sysdba=True)
    consulta, sentencia = consulta_oracle(conexion), sentencia_oracle(conexion)
    try:
        sid = sid_de_instancia(consulta)
    except oracledb.Error as error:
        pytest.skip(f"Oracle no disponible en {HOST}:{PUERTO}/{SERVICIO}: {error}")
    if not en_archivelog(consulta):
        pytest.skip("La base está en NOARCHIVELOG: activa ARCHIVELOG antes de ejecutar esta prueba")

    entorno = fabrica_desde_variables(os.environ, sys.platform)
    programador = programador_desde_variables(os.environ, sys.platform)
    sufijo = secrets.token_hex(4)
    directorio = f"PRUEBA_PROG_{sufijo.upper()}"
    ruta = f"/tmp/prueba_prog_{sufijo}"
    tabla_existia = bool(
        consulta("SELECT 1 FROM all_tables WHERE owner = 'SYSTEM' AND table_name = 'RESPALDOS_PROGRAMADOS'")
    )

    entorno.crear_carpeta(entorno.tipo_ruta(ruta))
    entorno.dar_permisos_a_oracle(entorno.tipo_ruta(ruta), sid)
    sentencia(f"CREATE OR REPLACE DIRECTORY {directorio} AS '{ruta}'")

    yield SimpleNamespace(
        consulta=consulta, sentencia=sentencia, sid=sid, entorno=entorno, programador=programador,
        directorio=directorio, ruta=ruta, sufijo=sufijo,
    )

    # limpieza: lo que el test no haya deshecho, en orden inverso a la creación
    try:
        for r in listar_respaldos(consulta, entorno)[0]:
            if r.directorio == directorio:
                eliminar_respaldo(consulta, entorno, directorio, r.base, sid)
    finally:
        _ejecutar_ignorando_errores(_Cursor(sentencia), f"DROP DIRECTORY {directorio}")
        docker("rm", "-rf", ruta)
        if not tabla_existia and not servicio.listar(consulta):
            _ejecutar_ignorando_errores(_Cursor(sentencia), f"DROP TABLE {servicio.TABLA} PURGE")


class _Cursor:
    """Adapta `sentencia` a la interfaz de `_ejecutar_ignorando_errores` (solo usa `execute`)."""

    def __init__(self, sentencia):
        self.execute = lambda sql: sentencia(sql)


def _crontab() -> list[str]:
    salida = subprocess.run(
        [CLI, "exec", "-u", "root", CONTENEDOR, "crontab", "-u", "oracle", "-l"],
        capture_output=True, text=True,
    )
    return salida.stdout.splitlines() if salida.returncode == 0 else []


def _ajenas(lineas: list[str]) -> list[str]:
    return [linea for linea in lineas if linea.strip()]


def _existe(ruta: str) -> bool:
    return docker("test", "-e", ruta).returncode == 0


def test_programar_ejecutar_reinstalar_y_eliminar_con_cron_y_rman_reales(contexto):
    c = contexto
    nombre = f"prueba-prog_{c.sufijo}"
    crontab_inicial = _ajenas(_crontab())
    id_prog = None
    try:
        # FP-3..FP-7, RN-7: programar
        creada = servicio.crear(
            c.consulta, c.sentencia, [Directorio(nombre=c.directorio, ruta=c.ruta)],
            Programacion(nombre, c.directorio, "TRANSACCIONAL", "DIARIO", "03:30"),
            c.entorno, c.programador, c.sid, "contenedor",
        )
        id_prog = creada.id
        script = f"{c.ruta}/scripts_programados/{nombre}.sh"
        rman = f"{c.ruta}/scripts_programados/{nombre}.rman"
        assert creada.ruta_script == script
        assert creada.ruta_rman == rman
        assert docker("test", "-f", rman).returncode == 0
        assert docker("test", "-x", script).returncode == 0  # el .sh es ejecutable
        marca = marca_cron(id_prog)
        lineas = _crontab()
        assert lineas.count(marca) == 1
        assert any(linea.startswith("30 3 * * *") and script in linea for linea in lineas), lineas
        assert docker("pgrep", "-x", "crond").returncode == 0  # RN-14
        [fila] = [p for p in servicio.listar(c.consulta) if p.id == id_prog]
        assert fila.ruta_script == script
        assert fila.ruta_rman == rman

        # FP-10, RN-6: ejecutar
        resultado = servicio.ejecutar(c.consulta, c.sentencia, c.entorno, id_prog, time.time)
        assert resultado.resultado == "Completo"
        assert resultado.log.strip()
        [respaldo] = [
            r for r in listar_respaldos(c.consulta, c.entorno)[0]
            if r.directorio == c.directorio and r.base.startswith(f"{nombre}_")
        ]
        assert respaldo.tipo == "RMAN"
        assert respaldo.estado == "Completo"
        assert any(a.nombre == f"{respaldo.base}.log" for a in respaldo.archivos)
        fila = servicio.obtener(c.consulta, id_prog)
        assert fila.ultimo_resultado == "Completo"
        assert fila.ultima_ejecucion is not None

        # FP-14, RN-13: perder la tarea y reinstalarla sin duplicar ni tocar otras líneas
        c.programador.eliminar(id_prog)
        assert marca not in _crontab()
        for _ in range(2):
            reinstalado = servicio.reinstalar(c.consulta, c.entorno, c.programador, c.sid)
            assert reinstalado.fallidas == ()
            assert reinstalado.reinstaladas == len(servicio.listar(c.consulta))
        lineas = _crontab()
        assert lineas.count(marca) == 1
        assert sum(script in linea for linea in lineas) == 1

        # FP-12, RN-12: eliminar deja todo limpio salvo los respaldos ya generados
        servicio.eliminar(c.consulta, c.sentencia, c.entorno, c.programador, id_prog)
        lineas = _crontab()
        assert marca not in lineas
        assert not any(script in linea for linea in lineas)
        assert _ajenas(lineas) == crontab_inicial
        assert not _existe(script) and not _existe(rman)
        assert servicio.obtener(c.consulta, id_prog) is None
        assert [
            r for r in listar_respaldos(c.consulta, c.entorno)[0]
            if r.directorio == c.directorio and r.base == respaldo.base
        ]
        id_prog = None
    finally:
        if id_prog is not None:  # el test falló a medias
            try:
                servicio.eliminar(c.consulta, c.sentencia, c.entorno, c.programador, id_prog)
            except Exception:
                c.programador.eliminar(id_prog)

