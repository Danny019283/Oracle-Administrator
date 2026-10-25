from collections.abc import Callable, Sequence
from typing import Any

from src.services.oracle_ejecucion import Sentencia

Consulta = Callable[..., Sequence[Sequence[Any]]]

MB = 1024 * 1024

SQL_INSTANCIA = """
SELECT i.instance_name, i.host_name, i.version_full, i.status,
       TO_CHAR(i.startup_time, 'DD/MM/YYYY HH24:MI:SS'), d.name, d.log_mode, d.open_mode
FROM v$instance i CROSS JOIN v$database d
"""

SQL_SGA = "SELECT name, value FROM v$sga ORDER BY name"

SQL_PGA = """
SELECT name, value FROM v$pgastat
WHERE name IN ('total PGA allocated', 'total PGA inuse', 'maximum PGA allocated')
ORDER BY name
"""

# Proporción de lecturas que se resolvieron en memoria (buffer cache).
SQL_BUFFER_CACHE = """
SELECT
  SUM(CASE WHEN name = 'physical reads cache' THEN value END),
  SUM(CASE WHEN name IN ('db block gets from cache', 'consistent gets from cache') THEN value END)
FROM v$sysstat
WHERE name IN ('physical reads cache', 'db block gets from cache', 'consistent gets from cache')
"""

SQL_LIBRARY_CACHE = "SELECT SUM(pinhits), SUM(pins) FROM v$librarycache"

SQL_CONTEO_SESIONES = """
SELECT COUNT(*), SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END)
FROM v$session WHERE type = 'USER'
"""

SQL_SESIONES = """
SELECT sid, serial#, username, status, osuser, machine, program,
       TO_CHAR(logon_time, 'DD/MM/YYYY HH24:MI:SS'), sql_id
FROM v$session
WHERE type = 'USER'
ORDER BY status, username, sid
"""

SQL_CONSULTAS = """
SELECT sql_id, parsing_schema_name, executions,
       ROUND(elapsed_time / 1000000, 3), ROUND(cpu_time / 1000000, 3),
       buffer_gets, disk_reads, SUBSTR(sql_text, 1, 300)
FROM v$sql
WHERE parsing_schema_name <> 'SYS'
ORDER BY elapsed_time DESC
FETCH FIRST :limite ROWS ONLY
"""

SQL_ESPERAS = """
SELECT event, wait_class, total_waits, ROUND(time_waited_micro / 1000000, 3)
FROM v$system_event
WHERE wait_class <> 'Idle'
ORDER BY time_waited_micro DESC
FETCH FIRST 10 ROWS ONLY
"""


class SesionInvalida(Exception):
    pass


def _porcentaje(parte: float | None, total: float | None) -> float | None:
    if not total:
        return None
    return round(100 * (parte or 0) / total, 2)


def resumen(consulta: Consulta) -> dict[str, Any]:
    instancia = consulta(SQL_INSTANCIA)[0]
    sga = [{"nombre": n, "mb": round((v or 0) / MB, 2)} for n, v in consulta(SQL_SGA)]
    pga = [{"nombre": n, "mb": round((v or 0) / MB, 2)} for n, v in consulta(SQL_PGA)]

    fisicas, logicas = consulta(SQL_BUFFER_CACHE)[0]
    aciertos, pins = consulta(SQL_LIBRARY_CACHE)[0]
    total_sesiones, activas = consulta(SQL_CONTEO_SESIONES)[0]

    buffer = None
    if logicas:
        buffer = round(100 * (1 - (fisicas or 0) / logicas), 2)

    return {
        "instancia": {
            "nombre": instancia[0],
            "host": instancia[1],
            "version": instancia[2],
            "estado": instancia[3],
            "inicio": instancia[4],
            "base_datos": instancia[5],
            "modo_log": instancia[6],
            "modo_apertura": instancia[7],
        },
        "memoria": {
            "sga": sga,
            "sga_total_mb": round(sum(f["mb"] for f in sga), 2),
            "pga": pga,
        },
        "indicadores": {
            "buffer_cache_hit": buffer,
            "library_cache_hit": _porcentaje(aciertos, pins),
            "sesiones_total": total_sesiones or 0,
            "sesiones_activas": activas or 0,
        },
    }


def listar_sesiones(consulta: Consulta) -> list[dict[str, Any]]:
    return [
        {
            "sid": sid,
            "serial": serial,
            "usuario": usuario,
            "estado": estado,
            "usuario_so": osuser,
            "maquina": maquina,
            "programa": programa,
            "conexion": conexion,
            "sql_id": sql_id,
        }
        for sid, serial, usuario, estado, osuser, maquina, programa, conexion, sql_id in consulta(
            SQL_SESIONES
        )
    ]


def consultas_costosas(consulta: Consulta, limite: int = 10) -> list[dict[str, Any]]:
    limite = max(1, min(limite, 50))
    return [
        {
            "sql_id": sql_id,
            "schema": schema,
            "ejecuciones": ejecuciones,
            "tiempo_total_s": tiempo,
            "cpu_s": cpu,
            "lecturas_logicas": logicas,
            "lecturas_disco": disco,
            "texto": texto,
        }
        for sql_id, schema, ejecuciones, tiempo, cpu, logicas, disco, texto in consulta(
            SQL_CONSULTAS, {"limite": limite}
        )
    ]


def principales_esperas(consulta: Consulta) -> list[dict[str, Any]]:
    return [
        {"evento": evento, "clase": clase, "esperas": total, "tiempo_s": tiempo}
        for evento, clase, total, tiempo in consulta(SQL_ESPERAS)
    ]


def terminar_sesion(sentencia: Sentencia, sid: int, serial: int) -> None:
    if not isinstance(sid, int) or not isinstance(serial, int) or sid <= 0 or serial < 0:
        raise SesionInvalida("El SID y el SERIAL# de la sesión deben ser números válidos")
    sentencia(f"ALTER SYSTEM KILL SESSION '{sid},{serial}' IMMEDIATE")
