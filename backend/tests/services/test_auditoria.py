import pytest

from src.services import auditoria


class ConsultaFalsa:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        for clave, filas in self.respuestas.items():
            if clave in sql:
                return filas
        return []


class SentenciaFalsa:
    def __init__(self):
        self.sqls = []

    def __call__(self, sql, params=None):
        self.sqls.append(sql)


def test_estado_indica_modo_mixto():
    consulta = ConsultaFalsa({"v$option": [("FALSE",)], "v$parameter": [("DB",)]})

    assert auditoria.estado(consulta) == {
        "modo": "Modo mixto (unificada y tradicional)",
        "audit_trail": "DB",
    }


def test_agrupa_las_politicas_y_marca_las_habilitadas():
    consulta = ConsultaFalsa(
        {
            "audit_unified_enabled_policies": [("AUD_EMP",)],
            "audit_unified_policies": [
                ("AUD_EMP", "DELETE", "HR", "EMPLOYEES"),
                ("AUD_EMP", "UPDATE", "HR", "EMPLOYEES"),
                ("ORA_LOGON_FAILURES", "LOGON", "NONE", "NONE"),
            ],
        }
    )

    politicas = auditoria.listar_politicas(consulta)

    assert politicas[0] == {
        "nombre": "AUD_EMP",
        "acciones": ["DELETE", "UPDATE"],
        "objetos": ["HR.EMPLOYEES"],
        "habilitada": True,
        "predefinida": False,
    }
    assert politicas[1]["predefinida"] is True and politicas[1]["objetos"] == []


def test_crea_politica_sobre_tabla_y_la_habilita():
    sentencia = SentenciaFalsa()

    nombre = auditoria.crear_politica(
        sentencia, "aud_emp", "tabla", ["delete", "update"], "hr", "employees"
    )

    assert nombre == "AUD_EMP"
    assert sentencia.sqls == [
        "CREATE AUDIT POLICY AUD_EMP ACTIONS DELETE ON HR.EMPLOYEES, UPDATE ON HR.EMPLOYEES",
        "AUDIT POLICY AUD_EMP",
    ]


def test_crea_politica_de_inicios_de_sesion_sin_habilitar():
    sentencia = SentenciaFalsa()

    auditoria.crear_politica(sentencia, "aud_logon", "sesion", [], habilitar=False)

    assert sentencia.sqls == ["CREATE AUDIT POLICY AUD_LOGON ACTIONS LOGON, LOGOFF"]


def test_valida_la_politica_y_reporta_todos_los_errores():
    with pytest.raises(auditoria.PoliticaInvalida) as error:
        auditoria.construir_politica("ORA_X", "tabla", ["DROP"], "", "EMP")

    assert len(error.value.errores) == 3


def test_no_elimina_politicas_predefinidas():
    sentencia = SentenciaFalsa()
    with pytest.raises(auditoria.PoliticaInvalida):
        auditoria.eliminar_politica(sentencia, "ORA_SECURECONFIG")
    assert sentencia.sqls == []


def test_habilita_deshabilita_y_elimina():
    sentencia = SentenciaFalsa()

    auditoria.deshabilitar_politica(sentencia, "aud_emp")
    auditoria.habilitar_politica(sentencia, "aud_emp")
    auditoria.eliminar_politica(sentencia, "aud_emp")

    assert sentencia.sqls == [
        "NOAUDIT POLICY AUD_EMP",
        "AUDIT POLICY AUD_EMP",
        "DROP AUDIT POLICY AUD_EMP",
    ]


def test_registros_filtra_con_variables_enlazadas():
    consulta = ConsultaFalsa(
        {"unified_audit_trail": [("24/10/2026 10:00:00", "HR", "DELETE", "HR", "EMPLOYEES", 0, "AUD_EMP", "delete from employees")]}
    )

    filas = auditoria.registros(consulta, politica="aud_emp", usuario="hr", limite=20)

    sql, params = consulta.llamadas[0]
    assert params == {"limite": 20, "politica": "AUD_EMP", "usuario": "HR"}
    assert "aud_emp" not in sql.lower().replace(":politica", "")
    assert filas[0]["accion"] == "DELETE" and filas[0]["codigo_retorno"] == 0
