import re
from collections.abc import Callable, Sequence
from typing import Any

from src.services.identificadores import normalizar_identificador
from src.services.oracle_ejecucion import Sentencia

Consulta = Callable[..., Sequence[Sequence[Any]]]

MB = 1024 * 1024

# Tamaño, espacio libre y número de archivos de cada tablespace. Los temporales
# guardan sus archivos en dba_temp_files y su espacio libre en dba_temp_free_space.
SQL_TABLESPACES = """
SELECT t.tablespace_name, t.contents, t.status, t.bigfile,
       NVL(a.bytes, 0), NVL(a.maximo, 0), NVL(l.bytes, 0), NVL(a.archivos, 0)
FROM dba_tablespaces t
LEFT JOIN (
  SELECT tablespace_name, SUM(bytes) bytes, SUM(GREATEST(maxbytes, bytes)) maximo, COUNT(*) archivos
  FROM dba_data_files GROUP BY tablespace_name
  UNION ALL
  SELECT tablespace_name, SUM(bytes), SUM(GREATEST(maxbytes, bytes)), COUNT(*)
  FROM dba_temp_files GROUP BY tablespace_name
) a ON a.tablespace_name = t.tablespace_name
LEFT JOIN (
  SELECT tablespace_name, SUM(bytes) bytes FROM dba_free_space GROUP BY tablespace_name
  UNION ALL
  SELECT tablespace_name, free_space FROM dba_temp_free_space
) l ON l.tablespace_name = t.tablespace_name
ORDER BY t.tablespace_name
"""

SQL_ARCHIVOS = """
SELECT file_id, file_name, bytes, autoextensible, maxbytes, status
FROM dba_data_files WHERE tablespace_name = :tablespace
UNION ALL
SELECT file_id, file_name, bytes, autoextensible, maxbytes, status
FROM dba_temp_files WHERE tablespace_name = :tablespace
ORDER BY 1
"""

# Los archivos nuevos se crean en la misma carpeta que los del tablespace SYSTEM,
# así el administrador solo elige el nombre del archivo, nunca una ruta.
SQL_CARPETA_DATAFILES = r"""
SELECT SUBSTR(file_name, 1, GREATEST(INSTR(file_name,'/',-1), INSTR(file_name,'\',-1)))
FROM dba_data_files WHERE tablespace_name = 'SYSTEM'
FETCH FIRST 1 ROWS ONLY
"""

TIPOS = {"PERMANENT", "TEMPORARY"}
ESTADOS = {"ONLINE", "OFFLINE", "READ ONLY", "READ WRITE"}
TABLESPACES_DEL_SISTEMA = {"SYSTEM", "SYSAUX"}

_TAMANO = re.compile(r"\d{1,6}[KMG]", re.IGNORECASE)
_ARCHIVO = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,59}\.dbf", re.IGNORECASE)


class TablespaceInvalido(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


class TablespaceNoEncontrado(Exception):
    pass


def _mb(valor: float | None) -> float:
    return round((valor or 0) / MB, 2)


def listar_tablespaces(consulta: Consulta) -> list[dict[str, Any]]:
    tablespaces = []
    for nombre, tipo, estado, bigfile, total, maximo, libre, archivos in consulta(SQL_TABLESPACES):
        usado = max(total - libre, 0)
        tablespaces.append(
            {
                "nombre": nombre,
                "tipo": tipo,
                "estado": estado,
                "bigfile": bigfile == "YES",
                "tamano_mb": _mb(total),
                "usado_mb": _mb(usado),
                "libre_mb": _mb(libre),
                "maximo_mb": _mb(maximo),
                "porcentaje_uso": round(100 * usado / total, 2) if total else 0,
                "archivos": archivos,
            }
        )
    return tablespaces


def _buscar(consulta: Consulta, tablespace: str) -> dict[str, Any]:
    nombre = normalizar_identificador(tablespace, "el tablespace")
    for ts in listar_tablespaces(consulta):
        if ts["nombre"] == nombre:
            return ts
    raise TablespaceNoEncontrado(f"El tablespace {nombre} no existe")


def listar_archivos(consulta: Consulta, tablespace: str) -> list[dict[str, Any]]:
    return [
        {
            "id": file_id,
            "archivo": archivo,
            "tamano_mb": _mb(tamano),
            "autoextensible": auto == "YES",
            "maximo_mb": _mb(maximo),
            "estado": estado,
        }
        for file_id, archivo, tamano, auto, maximo, estado in consulta(
            SQL_ARCHIVOS, {"tablespace": tablespace}
        )
    ]


def detalle_tablespace(consulta: Consulta, tablespace: str) -> dict[str, Any]:
    ts = _buscar(consulta, tablespace)
    return {**ts, "datafiles": listar_archivos(consulta, ts["nombre"])}


def carpeta_datafiles(consulta: Consulta) -> str:
    filas = consulta(SQL_CARPETA_DATAFILES)
    return filas[0][0] if filas else ""


def _tamano(valor: str, que: str, errores: list[str]) -> str:
    valor = (valor or "").strip().upper()
    if not _TAMANO.fullmatch(valor):
        errores.append(f"El {que} debe ser un tamaño como 100M, 500K o 1G")
    return valor


def _clausula_autoextend(
    autoextend: bool, siguiente: str, maximo: str, errores: list[str]
) -> str:
    if not autoextend:
        return "AUTOEXTEND OFF"
    siguiente = _tamano(siguiente, "incremento", errores)
    maximo = (maximo or "UNLIMITED").strip().upper()
    if maximo != "UNLIMITED" and not _TAMANO.fullmatch(maximo):
        errores.append("El tamaño máximo debe ser UNLIMITED o un tamaño como 2G")
    return f"AUTOEXTEND ON NEXT {siguiente} MAXSIZE {maximo}"


def _especificacion_archivo(
    consulta: Consulta,
    archivo: str,
    tamano: str,
    autoextend: bool,
    siguiente: str,
    maximo: str,
    errores: list[str],
) -> str:
    """Arma «'ruta' SIZE ... AUTOEXTEND ...» validando cada parte."""
    archivo = (archivo or "").strip()
    if not _ARCHIVO.fullmatch(archivo):
        errores.append(
            "El nombre del archivo debe empezar con una letra, usar solo letras, números o '_' "
            "y terminar en .dbf (por ejemplo ventas01.dbf)"
        )
    tamano = _tamano(tamano, "tamaño inicial", errores)
    autoextend_sql = _clausula_autoextend(autoextend, siguiente, maximo, errores)
    ruta = carpeta_datafiles(consulta) + archivo.lower()
    return f"'{ruta}' SIZE {tamano} {autoextend_sql}"


def crear_tablespace(
    consulta: Consulta,
    sentencia: Sentencia,
    nombre: str,
    tipo: str,
    archivo: str,
    tamano: str,
    autoextend: bool = True,
    siguiente: str = "10M",
    maximo: str = "UNLIMITED",
) -> str:
    errores = []
    try:
        nombre = normalizar_identificador(nombre, "el tablespace")
    except ValueError as error:
        errores.append(str(error))
    tipo = (tipo or "").strip().upper()
    if tipo not in TIPOS:
        errores.append("El tipo debe ser permanente o temporal")
    especificacion = _especificacion_archivo(
        consulta, archivo, tamano, autoextend, siguiente, maximo, errores
    )
    if errores:
        raise TablespaceInvalido(errores)

    if tipo == "TEMPORARY":
        sentencia(f"CREATE TEMPORARY TABLESPACE {nombre} TEMPFILE {especificacion}")
    else:
        sentencia(f"CREATE TABLESPACE {nombre} DATAFILE {especificacion}")
    return nombre


def agregar_archivo(
    consulta: Consulta,
    sentencia: Sentencia,
    tablespace: str,
    archivo: str,
    tamano: str,
    autoextend: bool = True,
    siguiente: str = "10M",
    maximo: str = "UNLIMITED",
) -> str:
    ts = _buscar(consulta, tablespace)
    errores: list[str] = []
    if ts["bigfile"]:
        errores.append("Un tablespace BIGFILE solo admite un archivo; redimensiónalo en su lugar")
    especificacion = _especificacion_archivo(
        consulta, archivo, tamano, autoextend, siguiente, maximo, errores
    )
    if errores:
        raise TablespaceInvalido(errores)

    clase = "TEMPFILE" if ts["tipo"] == "TEMPORARY" else "DATAFILE"
    sentencia(f"ALTER TABLESPACE {ts['nombre']} ADD {clase} {especificacion}")
    return ts["nombre"]


def _archivo_del_tablespace(consulta: Consulta, ts: dict[str, Any], file_id: int) -> str:
    """Valida que el archivo pertenezca al tablespace y devuelve su clase."""
    if file_id not in {a["id"] for a in listar_archivos(consulta, ts["nombre"])}:
        raise TablespaceInvalido([f"El archivo {file_id} no pertenece al tablespace {ts['nombre']}"])
    return "TEMPFILE" if ts["tipo"] == "TEMPORARY" else "DATAFILE"


def redimensionar_archivo(
    consulta: Consulta, sentencia: Sentencia, tablespace: str, file_id: int, tamano: str
) -> str:
    ts = _buscar(consulta, tablespace)
    errores: list[str] = []
    tamano = _tamano(tamano, "nuevo tamaño", errores)
    if errores:
        raise TablespaceInvalido(errores)
    clase = _archivo_del_tablespace(consulta, ts, file_id)
    sentencia(f"ALTER DATABASE {clase} {file_id} RESIZE {tamano}")
    return ts["nombre"]


def cambiar_autoextend(
    consulta: Consulta,
    sentencia: Sentencia,
    tablespace: str,
    file_id: int,
    autoextend: bool,
    siguiente: str = "10M",
    maximo: str = "UNLIMITED",
) -> str:
    ts = _buscar(consulta, tablespace)
    errores: list[str] = []
    clausula = _clausula_autoextend(autoextend, siguiente, maximo, errores)
    if errores:
        raise TablespaceInvalido(errores)
    clase = _archivo_del_tablespace(consulta, ts, file_id)
    sentencia(f"ALTER DATABASE {clase} {file_id} {clausula}")
    return ts["nombre"]


def cambiar_estado(consulta: Consulta, sentencia: Sentencia, tablespace: str, estado: str) -> str:
    ts = _buscar(consulta, tablespace)
    estado = " ".join((estado or "").split()).upper()
    if estado not in ESTADOS:
        raise TablespaceInvalido(["El estado debe ser ONLINE, OFFLINE, READ ONLY o READ WRITE"])
    if ts["tipo"] != "PERMANENT" or ts["nombre"] in TABLESPACES_DEL_SISTEMA:
        raise TablespaceInvalido(
            [
                f"El estado de {ts['nombre']} no se puede cambiar: solo se administran "
                "tablespaces permanentes que no sean SYSTEM ni SYSAUX"
            ]
        )
    sufijo = " NORMAL" if estado == "OFFLINE" else ""
    sentencia(f"ALTER TABLESPACE {ts['nombre']} {estado}{sufijo}")
    return ts["nombre"]
