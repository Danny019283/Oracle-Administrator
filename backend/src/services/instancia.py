from collections.abc import Callable, Sequence
from typing import Any

Consulta = Callable[..., Sequence[Sequence[Any]]]


def sid_de_instancia(consulta: Consulta) -> str:
    # INSTANCE_NAME es el SID real aunque la sesión use un servicio de PDB como XEPDB1
    return consulta("SELECT SYS_CONTEXT('USERENV','INSTANCE_NAME') FROM DUAL")[0][0]
