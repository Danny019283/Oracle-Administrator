import secrets
import time
from collections.abc import Callable

from src.services.expdp_runner import Conexion

INACTIVIDAD_MAXIMA = 15 * 60


class AlmacenSesiones:
    def __init__(self, reloj: Callable[[], float] = time.monotonic):
        self._reloj = reloj
        self._sesiones: dict[str, tuple[Conexion, float]] = {}

    def crear(self, conexion: Conexion) -> str:
        token = secrets.token_urlsafe(32)
        self._sesiones[token] = (conexion, self._reloj())
        return token

    def resolver(self, token: str) -> Conexion | None:
        sesion = self._sesiones.get(token)
        if sesion is None:
            return None
        conexion, ultimo_uso = sesion
        ahora = self._reloj()
        if ahora - ultimo_uso > INACTIVIDAD_MAXIMA:
            del self._sesiones[token]
            return None
        self._sesiones[token] = (conexion, ahora)
        return conexion

    def cerrar(self, token: str) -> None:
        self._sesiones.pop(token, None)
