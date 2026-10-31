import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from datetime import datetime
from typing import Any

import oracledb

from src.services.directorios import Directorio, DirectorioNoEncontrado
from src.services.entorno_oracle import ArchivoNoLegible, EntornoOracle, OperacionEntornoFallida
from src.services.errores_admin import codigo_error
from src.services.politica_respaldo import (
    Programacion,
    envoltorio,
    extension_envoltorio,
    script_rman,
    validar_programacion,
)
from src.services.programador_tareas import ProgramadorTareas, nombre_tarea
from src.services.respaldo import RespaldoFallido, SolicitudInvalida
from src.services.respaldo_full import SinArchivelog, en_archivelog
from src.services.rman_runner import ejecutar_rman

TABLA = "SYSTEM.RESPALDOS_PROGRAMADOS"
_COLUMNAS = (
    "ID, NOMBRE, POLITICA, FRECUENCIA, HORA, DIA, INTERVALO_HORAS, DIRECTORIO, "
    "RUTA_SCRIPT, RUTA_RMAN, ENTORNO, TAREA, CREADO, ULTIMA_EJECUCION, ULTIMO_RESULTADO"
)

_SCRIPT_POLITICA = """CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 7 DAYS;
CONFIGURE BACKUP OPTIMIZATION ON;
CONFIGURE CONTROLFILE AUTOBACKUP ON;
"""

Sentencia = Callable[..., None]
Consulta = Callable[..., Sequence[Sequence[Any]]]


@dataclass(frozen=True)
class RespaldoProgramado:
    id: int
    nombre: str
    politica: str
    frecuencia: str
    hora: str | None
    dia: int | None
    intervalo_horas: int | None
    directorio: str
    ruta_script: str
    ruta_rman: str
    entorno: str
    tarea: str
    creado: datetime
    ultima_ejecucion: datetime | None
    ultimo_resultado: str | None


def _es(error: Exception, codigo: str) -> bool:
    return codigo_error(str(error)) == codigo


def asegurar_tabla(sentencia: Sentencia) -> None:
    try:
        sentencia(
            f"CREATE TABLE {TABLA} ("
            "ID NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            "NOMBRE VARCHAR2(128) NOT NULL UNIQUE, "
            "POLITICA VARCHAR2(20) NOT NULL, "
            "FRECUENCIA VARCHAR2(20) NOT NULL, "
            "HORA VARCHAR2(5), "
            "DIA NUMBER, "
            "INTERVALO_HORAS NUMBER, "
            "DIRECTORIO VARCHAR2(128) NOT NULL, "
            "RUTA_SCRIPT VARCHAR2(1024) NOT NULL, "
            "RUTA_RMAN VARCHAR2(1024) NOT NULL, "
            "ENTORNO VARCHAR2(20) NOT NULL, "
            "TAREA VARCHAR2(128) NOT NULL, "
            "CREADO TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL, "
            "ULTIMA_EJECUCION TIMESTAMP, "
            "ULTIMO_RESULTADO VARCHAR2(20))",
            {},
        )
    except oracledb.Error as error:
        if not _es(error, "ORA-00955"):  # ya existe: idempotente (RNF-4)
            raise


def insertar(
    sentencia: Sentencia,
    consulta: Consulta,
    *,
    nombre: str,
    politica: str,
    frecuencia: str,
    hora: str | None,
    dia: int | None,
    intervalo_horas: int | None,
    directorio: str,
    ruta_script: str,
    ruta_rman: str,
    entorno: str,
    tarea: str,
) -> int:
    params = {
        "nombre": nombre, "politica": politica, "frecuencia": frecuencia,
        "hora": hora, "dia": dia, "intervalo_horas": intervalo_horas,
        "directorio": directorio, "ruta_script": ruta_script,
        "ruta_rman": ruta_rman, "entorno": entorno, "tarea": tarea,
    }
    sentencia(
        f"INSERT INTO {TABLA} (NOMBRE, POLITICA, FRECUENCIA, HORA, DIA, "
        "INTERVALO_HORAS, DIRECTORIO, RUTA_SCRIPT, RUTA_RMAN, ENTORNO, TAREA) "
        "VALUES (:nombre, :politica, :frecuencia, :hora, :dia, :intervalo_horas, "
        ":directorio, :ruta_script, :ruta_rman, :entorno, :tarea)",
        params,
    )
    filas = consulta(f"SELECT ID FROM {TABLA} WHERE NOMBRE = :nombre", {"nombre": nombre})
    return int(filas[0][0])


def _leer(consulta: Consulta, sql: str, params: dict[str, Any]) -> list[RespaldoProgramado]:
    try:
        return [RespaldoProgramado(*fila) for fila in consulta(sql, params)]
    except oracledb.Error as error:
        if _es(error, "ORA-00942"):  # tabla aún no creada (FA-8a)
            return []
        raise


def listar(consulta: Consulta) -> list[RespaldoProgramado]:
    return _leer(consulta, f"SELECT {_COLUMNAS} FROM {TABLA} ORDER BY ID", {})


def obtener(consulta: Consulta, id: int) -> RespaldoProgramado | None:
    filas = _leer(consulta, f"SELECT {_COLUMNAS} FROM {TABLA} WHERE ID = :id", {"id": id})
    return filas[0] if filas else None


def actualizar_resultado(sentencia: Sentencia, id: int, resultado: str) -> None:
    sentencia(
        f"UPDATE {TABLA} SET ULTIMA_EJECUCION = SYSTIMESTAMP, "
        "ULTIMO_RESULTADO = :resultado WHERE ID = :id",
        {"id": id, "resultado": resultado},
    )


def eliminar_fila(sentencia: Sentencia, id: int) -> None:
    sentencia(f"DELETE FROM {TABLA} WHERE ID = :id", {"id": id})


def aplicar_politica_global(entorno: EntornoOracle, sid: str) -> None:
    # CONFIGURE es idempotente: repetirlo deja la misma configuración (RNF-4)
    salida = ejecutar_rman(entorno, _SCRIPT_POLITICA, sid)
    if salida.codigo != 0:
        raise RespaldoFallido(salida.codigo, salida.texto, "rman")


@dataclass(frozen=True)
class ProgramacionCreada:
    id: int
    ruta_script: str
    ruta_rman: str


class ProgramacionDuplicada(Exception):
    def __init__(self):
        super().__init__("Ya existe una programación con ese nombre")


# el envoltorio .sh usa la ruta sin entrecomillar; el .bat sí, así que allí los espacios valen
_PROHIBIDOS = set("'\"$`;&|<>()*?!%\n\r[]{}")


def errores_ruta_directorio(ruta: str, tipo_ruta: type) -> list[str]:
    posix = issubclass(tipo_ruta, PurePosixPath)
    # en Windows solo el espacio simple es admisible; en POSIX tampoco la barra invertida
    malos = sorted({
        c for c in ruta
        if c in _PROHIBIDOS or (c.isspace() and (posix or c != " ")) or (posix and c == "\\")
    })
    if not malos:
        return []
    return [
        "La ruta del directorio contiene caracteres no admitidos para un respaldo programado: "
        + ", ".join(repr(c) for c in malos)
    ]


def _ruta_directorio(directorios: Sequence[Directorio], prog: Programacion, entorno: EntornoOracle):
    # la ruta sale siempre de all_directories, nunca del cliente (RN-5)
    for d in directorios:
        if d.nombre == prog.directorio:
            return entorno.tipo_ruta(d.ruta)
    raise DirectorioNoEncontrado(prog.directorio)


def _columnas_frecuencia(prog: Programacion) -> dict[str, Any]:
    if prog.frecuencia == "HORAS":
        return {"hora": None, "dia": None, "intervalo_horas": prog.intervalo_horas}
    dia = prog.dia_efectivo if prog.frecuencia in ("SEMANAL", "MENSUAL") else None
    return {"hora": prog.hora, "dia": dia, "intervalo_horas": None}


def crear(
    consulta: Consulta,
    sentencia: Sentencia,
    directorios: Sequence[Directorio],
    prog: Programacion,
    entorno: EntornoOracle,
    programador: ProgramadorTareas,
    sid: str,
    etiqueta_entorno: str,
) -> ProgramacionCreada:
    errores = validar_programacion(prog, [d.nombre for d in directorios])
    if errores:
        raise SolicitudInvalida(errores)
    destino = _ruta_directorio(directorios, prog, entorno)
    errores = errores_ruta_directorio(str(destino), entorno.tipo_ruta)
    if errores:
        raise SolicitudInvalida(errores)
    if not en_archivelog(consulta):
        raise SinArchivelog()
    if prog.nombre.lower() in {p.nombre.lower() for p in listar(consulta)}:
        raise ProgramacionDuplicada()
    carpeta = destino / "scripts_programados"
    asegurar_tabla(sentencia)
    aplicar_politica_global(entorno, sid)

    ruta_rman = carpeta / f"{prog.nombre}.rman"
    ruta_script = carpeta / f"{prog.nombre}{extension_envoltorio(destino)}"
    oracle_home = entorno.variable_de_entorno("ORACLE_HOME")
    texto_rman = script_rman(prog.politica, destino)
    try:
        if not oracle_home:
            raise ValueError("ORACLE_HOME vacío")
        texto_script = envoltorio(prog.nombre, sid, oracle_home, ruta_rman, destino)
    except ValueError as error:
        raise OperacionEntornoFallida(
            "No se pudo determinar ORACLE_HOME del servidor de Oracle (variable ausente o no válida)."
        ) from error

    # pasos de deshacer, solo de lo que este crear ya hizo; se ejecutan en orden inverso
    deshacer: list[Callable[[], None]] = []
    try:
        entorno.escribir_archivo(ruta_rman, texto_rman, False)
        deshacer.append(lambda: entorno.borrar_archivo(ruta_rman))
        entorno.escribir_archivo(ruta_script, texto_script, True)
        deshacer.append(lambda: entorno.borrar_archivo(ruta_script))
        # el nombre de la tarea lleva el ID de la fila (RN-13): primero la fila, luego la tarea
        id_nuevo = insertar(
            sentencia, consulta, nombre=prog.nombre, politica=prog.politica,
            frecuencia=prog.frecuencia, directorio=prog.directorio,
            ruta_script=str(ruta_script), ruta_rman=str(ruta_rman),
            entorno=etiqueta_entorno, tarea=f"OracleAdmin_{prog.nombre}",  # provisional: aún no hay ID
            **_columnas_frecuencia(prog),
        )
        deshacer.append(lambda: eliminar_fila(sentencia, id_nuevo))
        sentencia(
            f"UPDATE {TABLA} SET TAREA = :tarea WHERE ID = :id", {"id": id_nuevo, "tarea": nombre_tarea(id_nuevo)}
        )
        programador.instalar(id_nuevo, prog, str(ruta_script))
    except Exception as error:
        for paso in reversed(deshacer):
            try:
                paso()
            except Exception:  # best-effort: no tapa el error original
                pass
        if isinstance(error, oracledb.Error) and _es(error, "ORA-00001"):  # carrera con otra petición
            raise ProgramacionDuplicada() from error
        raise
    return ProgramacionCreada(id_nuevo, str(ruta_script), str(ruta_rman))


class ProgramacionNoEncontrada(Exception):
    def __init__(self):
        super().__init__("No existe la programación indicada")


class ScriptNoEncontrado(Exception):
    def __init__(self):
        super().__init__("El script de la programación ya no existe en disco; usa «Reinstalar tareas»")


@dataclass(frozen=True)
class ResultadoEjecucion:
    resultado: str
    log: str


_TOLERANCIA_RELOJ = 5  # segundos de desfase admitidos entre el reloj local y el del entorno


def _log_mas_reciente(entorno: EntornoOracle, carpeta: Any, nombre: str, desde: float | None = None) -> str | None:
    patron = re.compile(re.escape(nombre) + r"_\d{8}_\d{6}\.log", re.IGNORECASE)
    try:
        logs = [
            a for a in entorno.listar_archivos(carpeta)
            if patron.fullmatch(a.nombre) and (desde is None or a.modificado >= desde - _TOLERANCIA_RELOJ)
        ]
        if logs:
            return entorno.leer_archivo(carpeta / max(logs, key=lambda a: (a.nombre.upper(), a.modificado)).nombre)
    except (ArchivoNoLegible, OperacionEntornoFallida):
        pass
    return None


def ejecutar(
    consulta: Consulta,
    sentencia: Sentencia,
    entorno: EntornoOracle,
    id_programacion: int,
    reloj: Callable[[], float] | None = None,
) -> ResultadoEjecucion:
    fila = obtener(consulta, id_programacion)
    if fila is None:
        raise ProgramacionNoEncontrada()
    ruta = entorno.tipo_ruta(fila.ruta_script)
    # un fallo al listar se propaga: sin saber si el script existe no se ejecuta nada
    if ruta.name not in {a.nombre for a in entorno.listar_archivos(ruta.parent)}:
        raise ScriptNoEncontrado()
    inicio = reloj() if reloj else None
    salida = entorno.ejecutar_archivo(ruta)
    # el envoltorio pasa `log=` a RMAN: la salida real está en el log del DIRECTORY, no en stdout
    log = _log_mas_reciente(entorno, ruta.parent.parent, fila.nombre, inicio)
    texto = salida.texto if log is None else log
    resultado = "Completo" if salida.codigo == 0 else "Con errores"  # RN-11
    actualizar_resultado(sentencia, id_programacion, resultado)
    if salida.codigo != 0:
        raise RespaldoFallido(salida.codigo, texto, "rman")
    return ResultadoEjecucion(resultado, texto)


def eliminar(
    consulta: Consulta,
    sentencia: Sentencia,
    entorno: EntornoOracle,
    programador: ProgramadorTareas,
    id_programacion: int,
) -> str:
    fila = obtener(consulta, id_programacion)
    if fila is None:
        raise ProgramacionNoEncontrada()
    # primero la tarea: si falla no se borra nada, para no dejar una tarea huérfana (FA-12a)
    programador.eliminar(id_programacion)
    # solo los dos archivos de la programación; los respaldos generados no se tocan (RN-12)
    entorno.borrar_archivo(entorno.tipo_ruta(fila.ruta_script))
    entorno.borrar_archivo(entorno.tipo_ruta(fila.ruta_rman))
    # la fila va al final: si algo falló antes, "Eliminar" se puede reintentar
    eliminar_fila(sentencia, id_programacion)
    return fila.nombre


@dataclass(frozen=True)
class FalloReinstalacion:
    nombre: str
    mensaje: str


@dataclass(frozen=True)
class ResultadoReinstalacion:
    reinstaladas: int
    fallidas: tuple[FalloReinstalacion, ...]


def _reinstalar_una(fila: RespaldoProgramado, entorno: EntornoOracle, programador: ProgramadorTareas, sid: str) -> None:
    prog = Programacion(
        fila.nombre, fila.directorio, fila.politica, fila.frecuencia, fila.hora, fila.dia,
        *(() if fila.intervalo_horas is None else (fila.intervalo_horas,)),  # None: conserva el valor por defecto
    )
    ruta_script = entorno.tipo_ruta(fila.ruta_script)
    ruta_rman = entorno.tipo_ruta(fila.ruta_rman)
    destino = ruta_script.parent.parent
    try:
        presentes = {a.nombre for a in entorno.listar_archivos(ruta_script.parent)}
    except OperacionEntornoFallida:  # carpeta perdida (p. ej. contenedor recreado): se regenera todo
        presentes = set()
    # se preparan los textos antes de escribir nada, para no dejar la fila a medias
    pendientes: list[tuple[Any, str, bool]] = []
    if ruta_rman.name not in presentes:
        pendientes.append((ruta_rman, script_rman(prog.politica, destino), False))
    if ruta_script.name not in presentes:
        oracle_home = entorno.variable_de_entorno("ORACLE_HOME")
        if not oracle_home:
            raise OperacionEntornoFallida("No se pudo determinar ORACLE_HOME del servidor de Oracle")
        pendientes.append((ruta_script, envoltorio(prog.nombre, sid, oracle_home, ruta_rman, destino), True))
    for ruta, texto, ejecutable in pendientes:
        entorno.escribir_archivo(ruta, texto, ejecutable)
    programador.instalar(fila.id, prog, str(ruta_script))  # idempotente (RN-13, RNF-4)


def reinstalar(
    consulta: Consulta, entorno: EntornoOracle, programador: ProgramadorTareas, sid: str
) -> ResultadoReinstalacion:
    reinstaladas = 0
    fallidas: list[FalloReinstalacion] = []
    for fila in listar(consulta):
        try:
            _reinstalar_una(fila, entorno, programador, sid)
            reinstaladas += 1
        except Exception as error:  # una fila rota no aborta las demás (FA-14a)
            fallidas.append(FalloReinstalacion(fila.nombre, str(error)))
    return ResultadoReinstalacion(reinstaladas, tuple(fallidas))
