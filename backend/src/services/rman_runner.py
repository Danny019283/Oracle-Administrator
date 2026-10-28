from src.services.entorno_oracle import EntornoOracle, Salida


def ejecutar_rman(entorno: EntornoOracle, script: str) -> Salida:
    # `rman target /` usa la autenticación del SO donde corre Oracle: no hay contraseña.
    return entorno.ejecutar_herramienta(
        "rman", lambda ruta: ["target", "/", f"cmdfile={ruta}"], script,
        prefijo="rman", extension=".rman", variables={"ORACLE_SID": "XE"},
    )
