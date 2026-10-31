from src.services.entorno_oracle import ComandoHerramienta, EntornoOracle
from src.services.errores_oracle import explicar_error

APAGADA, NOMOUNT, MOUNT, ABIERTA = "APAGADA", "NOMOUNT", "MOUNT", "ABIERTA"

_STATUS = {"STARTED": NOMOUNT, "MOUNTED": MOUNT, "OPEN": ABIERTA}
_SIN_INSTANCIA = ("ORA-01034", "ORA-12162")

_CONSULTA = "SELECT status FROM v$instance;"

# (acción, estado actual) -> sentencias SQL fijas; el cliente solo elige la acción (RN-15).
_SCRIPTS = {
    ("APAGAR", NOMOUNT): "SHUTDOWN IMMEDIATE",
    ("APAGAR", MOUNT): "SHUTDOWN IMMEDIATE",
    ("APAGAR", ABIERTA): "SHUTDOWN IMMEDIATE",
    ("NOMOUNT", APAGADA): "STARTUP NOMOUNT",
    ("MOUNT", APAGADA): "STARTUP MOUNT",
    ("MOUNT", NOMOUNT): "ALTER DATABASE MOUNT;",
    ("ENCENDER", APAGADA): "STARTUP",
    ("ENCENDER", NOMOUNT): "ALTER DATABASE MOUNT;\nALTER DATABASE OPEN;",
    ("ENCENDER", MOUNT): "ALTER DATABASE OPEN;",
}


class AccionNoValida(Exception):
    def __init__(self, accion: str, estado: str):
        super().__init__(f"La acción {accion} no es válida con la base en estado {estado}")


class EstadoBaseFallido(Exception):
    def __init__(self, mensaje: str, log: str):
        super().__init__(mensaje)
        self.log = log
        self.explicacion = explicar_error(log)


def _sqlplus(entorno: EntornoOracle, sid: str, script: str, prefijo: str):
    return entorno.ejecutar(
        ComandoHerramienta(
            "sqlplus", lambda ruta: ["-S", "/ as sysdba", f"@{ruta}"], script,
            prefijo=prefijo, extension=".sql", variables={"ORACLE_SID": sid},
        )
    )


def estado_actual(entorno: EntornoOracle, sid: str) -> str:
    salida = _sqlplus(entorno, sid, f"{_CONSULTA}\nEXIT\n", "estado_base")
    if any(codigo in salida.texto for codigo in _SIN_INSTANCIA):
        return APAGADA
    if salida.codigo == 0:
        for linea in salida.texto.splitlines():
            if linea.strip() in _STATUS:
                return _STATUS[linea.strip()]
    raise EstadoBaseFallido("No se pudo consultar el estado de la base", salida.texto)


def cambiar_estado(entorno: EntornoOracle, sid: str, accion: str) -> str:
    estado = estado_actual(entorno, sid)
    sentencias = _SCRIPTS.get((accion, estado))
    if sentencias is None:
        raise AccionNoValida(accion, estado)
    script = f"WHENEVER SQLERROR EXIT SQL.SQLCODE\n{sentencias}\nEXIT\n"
    salida = _sqlplus(entorno, sid, script, "estado_base")
    if salida.codigo != 0:
        raise EstadoBaseFallido("No se pudo cambiar el estado de la base", salida.texto)
    return salida.texto
