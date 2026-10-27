import pytest

from src.services import tuning

MB = 1024 * 1024


class ConsultaFalsa:
    def __init__(self):
        self.llamadas = []

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))
        if "dba_users" in sql:
            return [("HR",)]
        if "dba_tablespaces" in sql:
            return [
                ("USERS", "PERMANENT", "ONLINE", "NO", 100 * MB, 100 * MB, 25 * MB, 1),
                ("HISTORICO", "PERMANENT", "READ ONLY", "NO", 100 * MB, 100 * MB, 25 * MB, 1),
                ("TEMP", "TEMPORARY", "ONLINE", "NO", 20 * MB, 20 * MB, 18 * MB, 1),
            ]
        if "dba_tab_statistics" in sql:
            return [
                ("EMPLOYEES", 107, 5, 69, "20/10/2026 08:00:00", "NO"),
                ("JOBS", None, None, None, None, None),
            ]
        if "dba_tab_columns" in sql:
            return [("EMPLOYEE_ID", "NUMBER"), ("LAST_NAME", "VARCHAR2"), ("Mi Columna", "NUMBER")]
        if "dba_indexes" in sql:
            return [
                ("HR", "EMP_EMP_ID_PK", "UNIQUE", "NORMAL", "VALID", "USERS", "20/10/2026", 107, 0, "EMPLOYEE_ID", "EMP_EMP_ID_PK"),
                ("HR", "EMP_NAME_IX", "NONUNIQUE", "NORMAL", "VALID", "USERS", "20/10/2026", 102, 0, "LAST_NAME", None),
            ]
        return []


class SentenciaFalsa:
    def __init__(self):
        self.llamadas = []

    @property
    def sqls(self):
        return [sql for sql, _ in self.llamadas]

    def __call__(self, sql, params=None):
        self.llamadas.append((sql, params))


class SesionFalsa:
    def __init__(self, texto=None, filas=None):
        self.pasos = []
        self.texto = texto or [("Plan hash value: 1",)]
        self.filas = filas or []

    def __call__(self, pasos):
        self.pasos = list(pasos)
        resultados = [None] * (len(pasos) - 2)
        return resultados + [self.texto, self.filas]


def test_catalogos_con_schemas_y_tablespaces_permanentes_online():
    assert tuning.catalogos(ConsultaFalsa()) == {"schemas": ["HR"], "tablespaces": ["USERS"]}


def test_lista_tablas_con_sus_estadisticas():
    tablas = tuning.listar_tablas(ConsultaFalsa(), "hr")

    assert tablas[0] == {
        "tabla": "EMPLOYEES",
        "filas": 107,
        "bloques": 5,
        "largo_promedio": 69,
        "analizada": "20/10/2026 08:00:00",
        "obsoletas": False,
    }
    assert tablas[1]["analizada"] is None


def test_schema_de_oracle_no_se_administra():
    with pytest.raises(tuning.ObjetoNoEncontrado):
        tuning.listar_tablas(ConsultaFalsa(), "SYS")


def test_tabla_inexistente():
    with pytest.raises(tuning.ObjetoNoEncontrado):
        tuning.listar_indices(ConsultaFalsa(), "HR", "NOEXISTE")


def test_recolecta_estadisticas_de_una_tabla_con_variables_enlazadas():
    sentencia = SentenciaFalsa()

    objetivo = tuning.recolectar_estadisticas(ConsultaFalsa(), sentencia, "hr", "employees")

    assert objetivo == "HR.EMPLOYEES"
    sql, params = sentencia.llamadas[0]
    assert "GATHER_TABLE_STATS" in sql
    assert params == {"schema": "HR", "tabla": "EMPLOYEES"}


def test_recolecta_estadisticas_de_todo_el_schema():
    sentencia = SentenciaFalsa()

    objetivo = tuning.recolectar_estadisticas(ConsultaFalsa(), sentencia, "HR")

    assert objetivo == "HR"
    sql, params = sentencia.llamadas[0]
    assert "GATHER_SCHEMA_STATS" in sql
    assert params == {"schema": "HR"}


def test_plan_ejecuta_explain_y_lee_plan_table_en_la_misma_sesion():
    sesion = SesionFalsa(
        texto=[("Plan hash value: 1",), ("| 0 | SELECT STATEMENT |",)],
        filas=[
            (0, None, 0, "SELECT STATEMENT", None, None, None, 3, 107, 7000, None, None),
            (1, 0, 1, "TABLE ACCESS", "FULL", "HR", "EMPLOYEES", 3, 107, 7000, None, '"SALARY">1000'),
        ],
    )

    plan = tuning.plan_ejecucion(ConsultaFalsa(), sesion, "select * from hr.employees where salary > 1000;")

    assert sesion.pasos[0] == ("EXPLAIN PLAN FOR select * from hr.employees where salary > 1000", None)
    assert "DBMS_XPLAN.DISPLAY" in sesion.pasos[1][0]
    assert "plan_table" in sesion.pasos[2][0]
    assert plan["texto"] == ["Plan hash value: 1", "| 0 | SELECT STATEMENT |"]
    assert plan["operaciones"][1]["objeto"] == "EMPLOYEES"
    assert plan["operaciones"][1]["filtro"] == '"SALARY">1000'
    assert "TABLE ACCESS FULL" in plan["observaciones"][0]


def test_plan_en_otro_schema_cambia_el_schema_actual():
    sesion = SesionFalsa()

    tuning.plan_ejecucion(ConsultaFalsa(), sesion, "SELECT * FROM employees", schema="hr")

    assert sesion.pasos[0] == ("ALTER SESSION SET CURRENT_SCHEMA = HR", None)
    assert sesion.pasos[1][0] == "EXPLAIN PLAN FOR SELECT * FROM employees"


def test_plan_avisa_si_faltan_estadisticas():
    sesion = SesionFalsa(texto=[("Note",), ("   - dynamic statistics used: dynamic sampling (level=2)",)])

    plan = tuning.plan_ejecucion(ConsultaFalsa(), sesion, "SELECT 1 FROM dual")

    assert any("Estadísticas" in o for o in plan["observaciones"])


@pytest.mark.parametrize("sql", ["", "   ;", "DROP TABLE hr.employees", "BEGIN NULL; END;", "x" * 20001])
def test_plan_rechaza_sentencias_que_no_se_pueden_explicar(sql):
    sesion = SesionFalsa()

    with pytest.raises(tuning.SolicitudTuningInvalida):
        tuning.plan_ejecucion(ConsultaFalsa(), sesion, sql)
    assert sesion.pasos == []


def test_lista_indices_con_columnas_y_restriccion():
    indices = tuning.listar_indices(ConsultaFalsa(), "HR", "EMPLOYEES")

    assert indices[0]["restriccion"] == "EMP_EMP_ID_PK"
    assert indices[0]["unico"] is True
    assert indices[1]["columnas"] == "LAST_NAME"
    assert indices[1]["restriccion"] is None


def test_crea_indice_compuesto_en_un_tablespace():
    sentencia = SentenciaFalsa()

    nombre = tuning.crear_indice(
        ConsultaFalsa(), sentencia, "hr", "employees", "emp_nombre_ix",
        ["last_name", "employee_id"], unico=False, tablespace="users",
    )

    assert nombre == "HR.EMP_NOMBRE_IX"
    assert sentencia.sqls == [
        "CREATE INDEX HR.EMP_NOMBRE_IX ON HR.EMPLOYEES (LAST_NAME, EMPLOYEE_ID) TABLESPACE USERS"
    ]


def test_crea_indice_unico_sin_tablespace():
    sentencia = SentenciaFalsa()

    tuning.crear_indice(ConsultaFalsa(), sentencia, "HR", "EMPLOYEES", "EMP_U", ["EMPLOYEE_ID"], unico=True)

    assert sentencia.sqls == ["CREATE UNIQUE INDEX HR.EMP_U ON HR.EMPLOYEES (EMPLOYEE_ID)"]


def test_crear_indice_reune_los_errores():
    sentencia = SentenciaFalsa()

    with pytest.raises(tuning.SolicitudTuningInvalida) as error:
        tuning.crear_indice(
            ConsultaFalsa(), sentencia, "HR", "EMPLOYEES", "",
            ["SALARIO", "LAST_NAME", "LAST_NAME", "Mi Columna"], tablespace="HISTORICO",
        )

    assert error.value.errores == [
        "Debes ingresar el nombre de el índice",
        "La columna SALARIO no existe en HR.EMPLOYEES",
        "La columna MI COLUMNA no existe en HR.EMPLOYEES",
        "No puedes repetir una columna en el mismo índice",
        "Debes elegir un tablespace permanente y ONLINE",
    ]
    assert sentencia.sqls == []


def test_crear_indice_sin_columnas():
    with pytest.raises(tuning.SolicitudTuningInvalida) as error:
        tuning.crear_indice(ConsultaFalsa(), SentenciaFalsa(), "HR", "EMPLOYEES", "IX", [])

    assert error.value.errores == ["Debes elegir al menos una columna"]


def test_elimina_indice_normal():
    sentencia = SentenciaFalsa()

    tuning.eliminar_indice(ConsultaFalsa(), sentencia, "HR", "EMPLOYEES", "emp_name_ix")

    assert sentencia.sqls == ["DROP INDEX HR.EMP_NAME_IX"]


def test_no_elimina_indice_de_llave_primaria():
    sentencia = SentenciaFalsa()

    with pytest.raises(tuning.SolicitudTuningInvalida):
        tuning.eliminar_indice(ConsultaFalsa(), sentencia, "HR", "EMPLOYEES", "EMP_EMP_ID_PK")
    assert sentencia.sqls == []


def test_eliminar_indice_inexistente():
    with pytest.raises(tuning.ObjetoNoEncontrado):
        tuning.eliminar_indice(ConsultaFalsa(), SentenciaFalsa(), "HR", "EMPLOYEES", "NADA")
