import secrets

from src.services.expdp_runner import Conexion


class AlmacenSesiones:
    def __init__(self):
        self._sesiones: dict[str, Conexion] = {}

    def crear(self, conexion: Conexion) -> str:
        token = secrets.token_urlsafe(32)
        self._sesiones[token] = conexion
        return token

    def resolver(self, token: str) -> Conexion | None:
        return self._sesiones.get(token)

    def cerrar(self, token: str) -> None:
        self._sesiones.pop(token, None)
