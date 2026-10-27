"""Dependencias y respuestas compartidas por Performance, Auditoría y Seguridad."""

from collections.abc import Callable
from typing import Any

import oracledb
from fastapi import Depends
from fastapi.responses import JSONResponse

from src.api.respaldos import obtener_conexion
from src.services.auditoria import PoliticaInvalida
from src.services.errores_admin import explicar_error_admin
from src.services.expdp_runner import Conexion
from src.services.identificadores import IdentificadorInvalido
from src.services.oracle_conexion import consulta_oracle
from src.services.oracle_ejecucion import sentencia_oracle
from src.services.performance import SesionInvalida
from src.services.seguridad import SolicitudInvalida, UsuarioNoAdministrable


def obtener_consulta_admin(conexion: Conexion = Depends(obtener_conexion)):
    return consulta_oracle(conexion)


def obtener_sentencia(conexion: Conexion = Depends(obtener_conexion)):
    return sentencia_oracle(conexion)


def responder(accion: Callable[[], Any]):
    """Ejecuta la acción y traduce los errores a respuestas uniformes.

    - 422 {"errores": [...]} cuando la solicitud no es válida.
    - 404 {"detail"} cuando el usuario no se puede administrar.
    - 500 {"mensaje", "explicacion", "error"} cuando Oracle rechaza la operación.
    """
    try:
        return accion()
    except (PoliticaInvalida, SolicitudInvalida) as error:
        return JSONResponse(status_code=422, content={"errores": error.errores})
    except (IdentificadorInvalido, SesionInvalida) as error:
        return JSONResponse(status_code=422, content={"errores": [str(error)]})
    except UsuarioNoAdministrable as error:
        return JSONResponse(status_code=404, content={"detail": str(error)})
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
