import pytest

from src.services import performance

MB = 1024 * 1024


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


def consulta_resumen():
    return ConsultaFalsa(
        {
            "v$instance": [("XE", "srv", "21.3.0.0.0", "OPEN", "20/10/2026 08:00:00", "XE", "ARCHIVELOG", "READ WRITE")],
            "v$sga": [("Database Buffers", 600 * MB), ("Fixed Size", 9 * MB)],
            "v$pgastat": [("total PGA allocated", 200 * MB)],
            "v$sysstat": [(10, 1000)],
            "v$librarycache": [(950, 1000)],
            "v$session": [(7, 2)],
        }
    )


def test_resumen_calcula_memoria_en_mb_e_indicadores():
    datos = performance.resumen(consulta_resumen())

    assert datos["instancia"]["estado"] == "OPEN"
    assert datos["instancia"]["modo_log"] == "ARCHIVELOG"
    assert datos["memoria"]["sga_total_mb"] == 609.0
    assert datos["memoria"]["pga"] == [{"nombre": "total PGA allocated", "mb": 200.0}]
    assert datos["indicadores"]["buffer_cache_hit"] == 99.0
    assert datos["indicadores"]["library_cache_hit"] == 95.0
    assert datos["indicadores"] == {
        "buffer_cache_hit": 99.0,
        "library_cache_hit": 95.0,
        "sesiones_total": 7,
        "sesiones_activas": 2,
    }


def test_sin_lecturas_el_hit_ratio_queda_vacio():
    consulta = consulta_resumen()
    consulta.respuestas["v$sysstat"] = [(None, None)]
    consulta.respuestas["v$librarycache"] = [(None, 0)]

    indicadores = performance.resumen(consulta)["indicadores"]

    assert indicadores["buffer_cache_hit"] is None
    assert indicadores["library_cache_hit"] is None


def test_lista_solo_sesiones_de_usuario():
    consulta = ConsultaFalsa(
        {"v$session": [(25, 101, "HR", "ACTIVE", "emijo", "PC", "sqlplus.exe", "24/10/2026 10:00:00", "abc")]}
    )

    sesiones = performance.listar_sesiones(consulta)

    assert sesiones[0]["sid"] == 25 and sesiones[0]["serial"] == 101
    assert "type = 'USER'" in consulta.llamadas[0][0]


def test_las_consultas_costosas_limitan_la_cantidad():
    consulta = ConsultaFalsa({"v$sql": []})

    performance.consultas_costosas(consulta, limite=500)

    assert consulta.llamadas[0][1] == {"limite": 50}


def test_terminar_sesion_arma_el_kill_session():
    sentencia = SentenciaFalsa()

    performance.terminar_sesion(sentencia, 25, 101)

    assert sentencia.sqls == ["ALTER SYSTEM KILL SESSION '25,101' IMMEDIATE"]


def test_terminar_sesion_rechaza_valores_invalidos():
    with pytest.raises(performance.SesionInvalida):
        performance.terminar_sesion(SentenciaFalsa(), 0, 1)
