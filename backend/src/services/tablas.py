from src.services.respaldo import Consulta, SinObjetos, listar_objetos


class SinTablas(SinObjetos):
    pass


def listar_tablas(consulta: Consulta) -> list[str]:
    return listar_objetos(
        consulta,
        "SELECT table_name FROM user_tables ORDER BY table_name",
        "No hay tablas en el schema",
        SinTablas,
    )
