from src.services.entorno_oracle import ComandoHerramienta, EntornoOracle, Salida


def ejecutar_rman(entorno: EntornoOracle, script: str, sid: str, log=None) -> Salida:
    # `rman target /` usa la autenticación del SO donde corre Oracle: no hay contraseña.
    # `log=` hace que RMAN escriba su log en esa ruta (SPOOL LOG dentro del cmdfile lo deja vacío).
    extra = [f"log={log}"] if log else []
    return entorno.ejecutar(
        ComandoHerramienta(
            "rman", lambda ruta: ["target", "/", f"cmdfile={ruta}", *extra], script,
            prefijo="rman", extension=".rman", variables={"ORACLE_SID": sid},
        )
    )
