from src.services.instancia import sid_de_instancia


class ConsultaFalsa:
    def __init__(self, sid):
        self.sid = sid
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)
        return [(self.sid,)]


def test_consulta_el_nombre_de_la_instancia_con_sys_context():
    consulta = ConsultaFalsa("XE")

    assert sid_de_instancia(consulta) == "XE"
    assert "sys_context('userenv','instance_name')" in consulta.sqls[0].lower().replace(" ", "")
