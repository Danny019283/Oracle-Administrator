from src.services.respaldo import Consulta, SinObjetos, listar_objetos


class SinSchemas(SinObjetos):
    pass


def listar_schemas(consulta: Consulta) -> list[str]:
    return listar_objetos(
        consulta,
        "SELECT username FROM all_users WHERE oracle_maintained = 'N' "
        "AND (username = sys_context('userenv', 'current_user') "
        "OR EXISTS (SELECT 1 FROM session_roles "
        "WHERE role = 'DATAPUMP_EXP_FULL_DATABASE')) "
        "ORDER BY username",
        "No hay schemas de usuario",
        SinSchemas,
    )
