from src.services.expdp_runner import Ejecutor, Salida, ejecutar_con_archivo


def ejecutar_rman(contenedor: str, script: str, ejecutar: Ejecutor) -> Salida:
    # `rman target /` usa la autenticación del SO dentro del contenedor: no hay contraseña.
    return ejecutar_con_archivo(
        contenedor, "rman", script,
        lambda ruta: ["env", "ORACLE_SID=XE", "rman", "target", "/", f"cmdfile={ruta}"],
        ejecutar, extension=".rman",
    )
