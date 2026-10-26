import json

from src.api.respaldos import respuesta_respaldo_fallido, respuesta_solicitud_invalida
from src.services.respaldo import RespaldoFallido, SolicitudInvalida


def test_la_solicitud_invalida_se_convierte_en_422_con_todos_los_errores():
    respuesta = respuesta_solicitud_invalida(SolicitudInvalida(["falta A", "falta B"]))

    assert respuesta.status_code == 422
    assert json.loads(respuesta.body) == {"errores": ["falta A", "falta B"]}


def test_el_respaldo_fallido_se_convierte_en_500_con_mensaje_explicacion_y_log():
    respuesta = respuesta_respaldo_fallido(
        RespaldoFallido(5, "ORA-27038: el archivo creado ya existe")
    )

    assert respuesta.status_code == 500
    assert json.loads(respuesta.body) == {
        "mensaje": "El respaldo falló: expdp terminó con código 5",
        "explicacion": "Ya existe un archivo de respaldo con ese nombre en el directorio",
        "log": "ORA-27038: el archivo creado ya existe",
    }


def test_el_mensaje_del_respaldo_fallido_nombra_la_herramienta():
    respuesta = respuesta_respaldo_fallido(RespaldoFallido(1, "RMAN-06149: x", "rman"))

    assert json.loads(respuesta.body)["mensaje"] == "El respaldo falló: rman terminó con código 1"
