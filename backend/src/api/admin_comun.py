"""Dependencias y respuestas compartidas por los módulos de administración."""

from collections.abc import Callable
from typing import Any

import oracledb
from fastapi import Depends
from fastapi.responses import JSONResponse

from src.api.respaldos import obtener_conexion
from src.services.auditoria import PoliticaInvalida
from src.services.directorios import DirectorioInvalido, DirectorioNoEncontrado
from src.services.entorno_oracle import OperacionEntornoFallida
from src.services.errores_admin import explicar_error_admin
from src.services.expdp_runner import Conexion
from src.services.identificadores import IdentificadorInvalido
from src.services.oracle_conexion import consulta_oracle
from src.services.oracle_ejecucion import sentencia_oracle, sesion_oracle
from src.services.performance import SesionInvalida
from src.services.seguridad import SolicitudInvalida, UsuarioNoAdministrable
from src.services.tablespaces import TablespaceInvalido, TablespaceNoEncontrado
from src.services.tuning import ObjetoNoEncontrado, SolicitudTuningInvalida


def obtener_consulta_admin(conexion: Conexion = Depends(obtener_conexion)):
    return consulta_oracle(conexion)


def obtener_sentencia(conexion: Conexion = Depends(obtener_conexion)):
    return sentencia_oracle(conexion)


def obtener_sesion(conexion: Conexion = Depends(obtener_conexion)):
    return sesion_oracle(conexion)


def responder(accion: Callable[[], Any]):
    """Ejecuta la acción y traduce los errores a respuestas uniformes.

    - 422 {"errores": [...]} cuando la solicitud no es válida.
    - 404 {"detail"} cuando el usuario, tablespace, schema, tabla, índice o directorio no se puede administrar.
    - 500 {"mensaje", "explicacion", "error"} cuando Oracle rechaza la operación o fallan los permisos de la carpeta.
    """
    try:
        return accion()
    except (PoliticaInvalida, SolicitudInvalida, TablespaceInvalido, SolicitudTuningInvalida, DirectorioInvalido) as error:
        return JSONResponse(status_code=422, content={"errores": error.errores})
    except (IdentificadorInvalido, SesionInvalida) as error:
        return JSONResponse(status_code=422, content={"errores": [str(error)]})
    except (UsuarioNoAdministrable, TablespaceNoEncontrado, ObjetoNoEncontrado, DirectorioNoEncontrado) as error:
        return JSONResponse(status_code=404, content={"detail": str(error)})
    except OperacionEntornoFallida as error:
        texto = str(error).strip()
        return JSONResponse(
            status_code=500,
            content={
                "mensaje": "No se pudieron dar permisos a Oracle sobre la carpeta",
                "explicacion": "La carpeta debe existir y Oracle debe poder escribir en ella; en contenedor, creada o montada",
                "error": texto.splitlines()[0] if texto else "",
            },
        )
    except oracledb.Error as error:
        texto = str(error).strip()
        return JSONResponse(
            status_code=500,
            content={
                "mensaje": "Oracle rechazó la operación",
                "explicacion": explicar_error_admin(texto),
                "error": texto.splitlines()[0] if texto else "",
            },
        )
