import oracledb
import pytest

from tests.integration.conftest import HOST, PUERTO, SERVICIO, _ejecutar_ignorando_errores, _password_admin

TABLESPACE = "TEST_TS_OA"
ARCHIVO = "test_ts_oa01.dbf"
SCHEMA = "TEST_TUNING"


@pytest.fixture(scope="module")
def admin():
    """Cabeceras de SYSTEM y un schema de pruebas con una tabla; todo se borra al terminar."""
    password = _password_admin()
    if password is None:
        pytest.skip("Falta ORACLE_DATABASE_PASSWORD para preparar la base de pruebas")
    try:
        bd = oracledb.connect(user="system", password=password, dsn=f"{HOST}:{PUERTO}/{SERVICIO}")
    except oracledb.Error as error:
        pytest.skip(f"Oracle no disponible en {HOST}:{PUERTO}/{SERVICIO}: {error}")

    cursor = bd.cursor()

    def limpiar():
        _ejecutar_ignorando_errores(cursor, f"DROP USER {SCHEMA} CASCADE")
        _ejecutar_ignorando_errores(
            cursor, f"DROP TABLESPACE {TABLESPACE} INCLUDING CONTENTS AND DATAFILES"
        )

    limpiar()
    cursor.execute(f"CREATE USER {SCHEMA} NO AUTHENTICATION QUOTA UNLIMITED ON USERS DEFAULT TABLESPACE USERS")
    cursor.execute(f"CREATE TABLE {SCHEMA}.PEDIDOS (id NUMBER PRIMARY KEY, cliente VARCHAR2(50), monto NUMBER)")
    cursor.execute(
        f"INSERT INTO {SCHEMA}.PEDIDOS SELECT level, 'C' || MOD(level, 50), level * 10 "
        "FROM dual CONNECT BY level <= 500"
    )
    bd.commit()

    yield {"X-Oracle-User": "system", "X-Oracle-Password": password, "X-Oracle-Service": SERVICIO}

    limpiar()
    bd.close()


@pytest.mark.integration
def test_lista_tablespaces_con_uso_real(cliente, admin):
    respuesta = cliente.get("/tablespaces", headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    nombres = {t["nombre"]: t for t in respuesta.json()["tablespaces"]}
    assert {"SYSTEM", "SYSAUX", "USERS", "TEMP"} <= set(nombres)
    assert nombres["TEMP"]["tipo"] == "TEMPORARY"
    assert nombres["USERS"]["tamano_mb"] > 0
    assert respuesta.json()["carpeta"].endswith("/")


@pytest.mark.integration
def test_crea_modifica_y_cambia_el_estado_de_un_tablespace(cliente, admin):
    creado = cliente.post(
        "/tablespaces",
        json={"nombre": TABLESPACE, "tipo": "PERMANENT", "archivo": ARCHIVO, "tamano": "10M", "autoextend": False},
        headers=admin,
    )
    assert creado.status_code == 200, creado.text

    detalle = cliente.get(f"/tablespaces/{TABLESPACE}", headers=admin).json()
    assert detalle["datafiles"][0]["archivo"].endswith(ARCHIVO)
    assert detalle["datafiles"][0]["autoextensible"] is False
    file_id = detalle["datafiles"][0]["id"]

    base = f"/tablespaces/{TABLESPACE}/archivos/{file_id}"
    assert cliente.post(f"{base}/redimensionar", json={"tamano": "20M"}, headers=admin).status_code == 200
    assert cliente.post(f"{base}/autoextend", json={"autoextend": True}, headers=admin).status_code == 200
    detalle = cliente.get(f"/tablespaces/{TABLESPACE}", headers=admin).json()
    assert detalle["datafiles"][0]["tamano_mb"] == 20.0
    assert detalle["datafiles"][0]["autoextensible"] is True

    agregado = cliente.post(
        f"/tablespaces/{TABLESPACE}/archivos",
        json={"archivo": "test_ts_oa02.dbf", "tamano": "5M", "autoextend": False},
        headers=admin,
    )
    assert agregado.status_code == 200, agregado.text

    estado = f"/tablespaces/{TABLESPACE}/estado"
    assert cliente.post(estado, json={"estado": "READ ONLY"}, headers=admin).status_code == 200
    assert cliente.get(f"/tablespaces/{TABLESPACE}", headers=admin).json()["estado"] == "READ ONLY"
    assert cliente.post(estado, json={"estado": "READ WRITE"}, headers=admin).status_code == 200
    assert cliente.post(estado, json={"estado": "OFFLINE", "confirmar": True}, headers=admin).status_code == 200
    assert cliente.post(estado, json={"estado": "ONLINE"}, headers=admin).status_code == 200


@pytest.mark.integration
def test_crear_tablespace_repetido_explica_el_error(cliente, admin):
    solicitud = {"nombre": "USERS", "archivo": "otro_users.dbf", "tamano": "5M", "autoextend": False}

    respuesta = cliente.post("/tablespaces", json=solicitud, headers=admin)

    assert respuesta.status_code == 500
    assert respuesta.json()["error"].startswith("ORA-01543")


@pytest.mark.integration
def test_plan_de_ejecucion_real(cliente, admin):
    respuesta = cliente.post(
        "/tuning/plan",
        json={"sql": "SELECT * FROM pedidos WHERE cliente = 'C7'", "schema": SCHEMA},
        headers=admin,
    )

    assert respuesta.status_code == 200, respuesta.text
    plan = respuesta.json()
    assert any("Plan hash value" in linea for linea in plan["texto"])
    assert plan["operaciones"][0]["operacion"] == "SELECT STATEMENT"
    assert any(op["objeto"] == "PEDIDOS" for op in plan["operaciones"])


@pytest.mark.integration
def test_estadisticas_e_indices_reales(cliente, admin):
    recolectar = cliente.post(
        "/tuning/estadisticas", json={"schema": SCHEMA, "tabla": "PEDIDOS"}, headers=admin
    )
    assert recolectar.status_code == 200, recolectar.text
    tablas = cliente.get("/tuning/tablas", params={"schema": SCHEMA}, headers=admin).json()["tablas"]
    assert tablas[0]["filas"] == 500
    assert tablas[0]["analizada"]

    creado = cliente.post(
        "/tuning/indices",
        json={"schema": SCHEMA, "tabla": "PEDIDOS", "nombre": "PEDIDOS_CLIENTE_IX", "columnas": ["CLIENTE"]},
        headers=admin,
    )
    assert creado.status_code == 200, creado.text

    datos = cliente.get(
        "/tuning/indices", params={"schema": SCHEMA, "tabla": "PEDIDOS"}, headers=admin
    ).json()
    indices = {i["nombre"]: i for i in datos["indices"]}
    assert indices["PEDIDOS_CLIENTE_IX"]["columnas"] == "CLIENTE"
    llave = next(i for i in datos["indices"] if i["restriccion"])

    rechazado = cliente.post(
        "/tuning/indices/eliminar",
        json={"schema": SCHEMA, "tabla": "PEDIDOS", "nombre": llave["nombre"], "confirmar": True},
        headers=admin,
    )
    assert rechazado.status_code == 422

    eliminado = cliente.post(
        "/tuning/indices/eliminar",
        json={"schema": SCHEMA, "tabla": "PEDIDOS", "nombre": "PEDIDOS_CLIENTE_IX", "confirmar": True},
        headers=admin,
    )
    assert eliminado.status_code == 200, eliminado.text
