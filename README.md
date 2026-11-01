# Administrador Oracle

Entorno Docker con Oracle Database 21c Express Edition (`container-registry.oracle.com/database/express:21.3.0-xe`).

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) con Docker Compose v2 (`docker compose`).
  - **Windows:** Docker Desktop en ejecución.
  - **Linux:** Docker Engine y el plugin de Compose; tu usuario debe poder usar `docker` (grupo `docker`) o ejecutar los scripts con `sudo`.
- Acceso a `container-registry.oracle.com` para descargar la imagen (unos GB de descarga).

## Configuración

1. Copia el archivo de ejemplo y créalo como `.env`:

   - Linux: `cp .env-example .env`
   - Windows (cmd): `copy .env-example .env`

2. Edita `.env` y define la contraseña de los usuarios administradores (`SYS`, `SYSTEM`, `PDBADMIN`):

   ```
   ORACLE_DATABASE_PASSWORD=TuPasswordSegura
   ```

## Uso

Los scripts se ejecutan desde cualquier ubicación; ellos mismos se posicionan en la carpeta del proyecto.

### 1. Descargar la imagen

Solo hace falta la primera vez (o para actualizar la imagen).

| Sistema | Comando |
| ------- | ------- |
| Linux   | `./descargar-oracle21c.sh` |
| Windows | `descargar-oracle21c.bat` (doble clic o desde cmd/PowerShell) |

> En Linux, si el script no es ejecutable: `chmod +x *.sh`.

### 2. Levantar el contenedor

| Sistema | Comando |
| ------- | ------- |
| Linux   | `./levantar-oracle21c.sh` |
| Windows | `levantar-oracle21c.bat` |

El script inicia el contenedor `oracle21c` en segundo plano y espera hasta que Oracle esté listo (la primera vez puede tardar varios minutos). Al terminar muestra `Oracle listo en localhost:1521`.

En Windows, si tras 10 minutos (120 intentos cada 5 s) no está listo, el script termina con error; revisa los logs con `docker logs oracle21c`.

## Conexión

| Dato       | Valor |
| ---------- | ----- |
| Host       | `localhost` |
| Puerto     | `1521` |
| Service name | `XE` (CDB) / `XEPDB1` (PDB) |
| Usuario    | `SYS` (como `SYSDBA`), `SYSTEM` o `PDBADMIN` |
| Contraseña | la definida en `ORACLE_DATABASE_PASSWORD` del `.env` |
| Puerto EM Express | `5500` (`https://localhost:5500/em`) |

## Levantar la aplicación (backend + frontend)

La aplicación son dos procesos: el **backend** (FastAPI, puerto `8000`) y el **frontend** (Vite, puerto `5173`, que reenvía las llamadas al backend). Cada uno va en su propia terminal. Elige tu caso:

| Caso | Oracle | Backend corre en |
| ---- | ------ | ---------------- |
| [Linux con Docker](#linux-con-docker) | contenedor `oracle21c` | tu equipo Linux |
| [Linux local](#linux-local) | instalado en el equipo | tu equipo Linux |
| [Windows](#windows) | contenedor (Docker Desktop) o instalado en el equipo | tu equipo Windows |

Herramientas comunes a los tres casos:

- [`uv`](https://docs.astral.sh/uv/) (instala Python 3.14 por su cuenta): Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`; Windows `winget install astral-sh.uv`.
- [Node.js](https://nodejs.org/) LTS con `npm`: Windows `winget install OpenJS.NodeJS.LTS`.

Cuando todo está arriba, abre <http://localhost:5173> e inicia sesión (`SYS` como `SYSDBA` para respaldos RMAN, programados y ARCHIVELOG). Para parar, `Ctrl+C` en cada terminal.

### Linux con Docker

1. Configura la contraseña (ver [Configuración](#configuración)): `cp .env-example .env` y edita `ORACLE_DATABASE_PASSWORD`.
2. Baja la imagen (solo la primera vez) y levanta Oracle:

   ```bash
   chmod +x *.sh
   ./descargar-oracle21c.sh
   ./levantar-oracle21c.sh      # espera a "Oracle listo en localhost:1521"
   ```

3. Backend (terminal 1). No hace falta definir variables: el modo por defecto es `contenedor`.

   ```bash
   cd backend
   uv sync
   uv run fastapi dev main.py   # http://localhost:8000
   ```

4. Frontend (terminal 2):

   ```bash
   cd frontend
   npm install
   npm run dev                  # http://localhost:5173
   ```

Si usas Podman: `export ORACLE_CONTAINER_CLI=podman` antes de arrancar el backend. Los respaldos programados quedan en el `crontab` del contenedor; tras `docker compose down` hay que pulsar «Reinstalar tareas» (ver [Respaldos programados](#respaldos-programados-rman)).

### Linux local

Oracle ya instalado en el equipo (no Docker).

1. Requisitos (detalle en [Modo local](#modo-local-windows-y-linux)): `expdp`, `impdp`, `sqlplus` y `rman` en el `PATH`; `ORACLE_HOME` definido; tu usuario en el grupo `dba`; `cron` instalado y activo para los respaldos programados.
2. Backend (terminal 1). Las variables se definen en la misma terminal, el backend no lee `.env`:

   ```bash
   export ORACLE_ENTORNO=local
   export ORACLE_HOME=/ruta/a/oracle
   export ORACLE_FRA_DIRECTORIO=/ruta/a/fast_recovery_area   # opcional, ver Modo local
   cd backend
   uv sync
   uv run fastapi dev main.py
   ```

3. Frontend (terminal 2):

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Windows

Hay dos formas; el frontend es igual en ambas.

**A) Oracle en Docker Desktop.** Con Docker Desktop en ejecución:

```bat
copy .env-example .env
:: edita .env y define ORACLE_DATABASE_PASSWORD
descargar-oracle21c.bat
levantar-oracle21c.bat
```

Backend (terminal 1, modo `contenedor` por defecto, sin variables):

```bat
cd backend
uv sync
uv run fastapi dev main.py
```

**B) Oracle instalado en Windows.** Abre PowerShell **como administrador** (el backend crea las tareas programadas con `schtasks`):

```powershell
$env:ORACLE_ENTORNO = "local"
$env:ORACLE_HOME = "C:\app\oracle\product\21c\dbhomeXE"            # tu ruta real
$env:ORACLE_FRA_DIRECTORIO = "C:\app\oradata\fast_recovery_area"   # opcional
cd backend
uv sync
uv run fastapi dev main.py
```

Requisitos: `rman`, `sqlplus`, `expdp` e `impdp` en el `PATH`, y tu usuario en el grupo `ORA_DBA`. Las tareas se registran como `OracleAdmin_<id>` y se ejecutan con la cuenta `SYSTEM`. El modo local en Windows aún no se ha probado en un equipo real: si algo falla, revisa el mensaje del backend.

Frontend en ambos casos (terminal 2):

```bat
cd frontend
npm install
npm run dev
```

## Modo local (Windows y Linux)

El backend funciona igual con Oracle en Docker, en Linux local o en Windows local. Por defecto asume el contenedor; para usar una instalación de Oracle del propio equipo define `ORACLE_ENTORNO=local`.

| Variable | Valor | Defecto |
| -------- | ----- | ------- |
| `ORACLE_ENTORNO` | `contenedor` o `local` | `contenedor` |
| `ORACLE_HOST` | host de Oracle | `localhost` |
| `ORACLE_PORT` | puerto del listener | `1521` |
| `ORACLE_CONTAINER` | nombre del contenedor (solo `contenedor`) | `oracle21c` |
| `ORACLE_CONTAINER_CLI` | `docker` o `podman` (solo `contenedor`) | `docker` |
| `ORACLE_FRA_DIRECTORIO` | carpeta de la FRA para activar ARCHIVELOG | ver abajo |

Sin `ORACLE_FRA_DIRECTORIO`, en modo `contenedor` se usa la ruta del contenedor y en modo `local` se deriva de la carpeta de datafiles de `SYSTEM` (su carpeta padre más `fast_recovery_area`). Si no se puede derivar, activar ARCHIVELOG responde un error que pide definirla.

Requisitos del modo local:

- `expdp`, `impdp`, `sqlplus` y `rman` en el `PATH` de quien ejecuta el backend.
- `sqlplus` y `rman` entran con autenticación del sistema operativo: en Windows el usuario debe pertenecer al grupo `ORA_DBA`; en Linux al grupo `dba`, con `ORACLE_HOME` definido.

El backend **no lee el archivo `.env`**: las variables deben estar definidas en la terminal desde la que se arranca.

```powershell
# PowerShell
$env:ORACLE_ENTORNO = "local"
$env:ORACLE_FRA_DIRECTORIO = "C:\app\oradata\fast_recovery_area"
```

```bat
:: cmd
set ORACLE_ENTORNO=local
set ORACLE_FRA_DIRECTORIO=C:\app\oradata\fast_recovery_area
```

```bash
# bash
export ORACLE_ENTORNO=local
export ORACLE_FRA_DIRECTORIO=/opt/oracle/fast_recovery_area
```

## Respaldos programados (RMAN)

Permite programar respaldos RMAN recurrentes. Solo aplica a RMAN (no a tablas ni schemas con Data Pump) y exige sesión SYSDBA y la base en ARCHIVELOG.

### Qué hace y dónde está

- **Programar:** en «Creación de respaldos → Full», marca el check «Programar respaldo». Elige DIRECTORY, nombre, política, frecuencia y hora, y pulsa «Programar».
- **Administrar:** en «Administración de archivos de respaldos y directorios», la sección «Respaldos programados» lista las programaciones y ofrece Ejecutar, Eliminar (con confirmación) y «Reinstalar tareas».

| Campo | Valores |
| ----- | ------- |
| Política | Full, Incremental, Transaccional |
| Frecuencia | Diario, Semanal (día 0 = domingo a 6 = sábado, por defecto domingo), Mensual (día 1 a 28, por defecto 1) |
| Cada N horas | solo Transaccional; N de 1 a 23 (por defecto 2), en el minuto 0 |
| Hora | `HH:MM` en 24 h |

Cada política genera un `.rman` fijo:

| Política | Contenido |
| -------- | --------- |
| Full | `BACKUP INCREMENTAL LEVEL 0 DATABASE` (tag `PROG_FULL_L0`), luego `CROSSCHECK BACKUP`, `CROSSCHECK ARCHIVELOG ALL` y `DELETE NOPROMPT OBSOLETE` |
| Incremental | `BACKUP INCREMENTAL LEVEL 1 DATABASE` (tag `PROG_INCREMENTAL_L1`), luego `BACKUP ARCHIVELOG ALL DELETE INPUT` |
| Transaccional | `SQL 'ALTER SYSTEM SWITCH LOGFILE'`, luego `BACKUP ARCHIVELOG ALL DELETE INPUT` (tag `PROG_TRANSACCIONAL`) |

Al programar se aplica una vez la política global de RMAN (repetirla no hace daño): `CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 7 DAYS`, `CONFIGURE BACKUP OPTIMIZATION ON` y `CONFIGURE CONTROLFILE AUTOBACKUP ON`. Esta configuración no se revierte al eliminar una programación.

Cada ejecución genera `<nombre>_AAAAMMDD_HHMMSS` (piezas `<base>_%d_%s_%p.dbf` y log `<base>.log`), así que los respaldos programados aparecen en la lista de respaldos como RMAN con su `.log`. Eliminar una programación no borra los respaldos que ya generó.

### Requisitos por entorno

| Entorno | Programador | Requisitos |
| ------- | ----------- | ---------- |
| Linux local (`ORACLE_ENTORNO=local`) | `cron` (`crontab` del usuario que ejecuta el backend) | `crontab` y `rman` disponibles; `ORACLE_HOME` definido; usuario en el grupo `dba` |
| Windows local | `schtasks`: tarea `OracleAdmin_<id>` creada con `/RU SYSTEM` y `/F` | El backend debe ejecutarse con privilegios para crear tareas, y la cuenta de la tarea debe poder entrar `/ as sysdba` (p. ej. SYSTEM o un miembro del grupo `ORA_DBA`) |
| Docker (`contenedor`) | `crontab` del usuario `oracle` dentro del contenedor | `crond` lo arrancan `levantar-oracle21c.sh/.bat` y la app antes de programar, eliminar y reinstalar (Ejecutar no lo arranca) |

En cron la tarea se identifica con la marca `# oracle-admin:<id>`; instalar o reinstalar nunca la duplica.

### Scripts y tabla

- Los scripts quedan en `<ruta del DIRECTORY>/scripts_programados/<nombre>.rman` y `<nombre>.sh` (Linux y contenedor) o `<nombre>.bat` (Windows). No llevan contraseñas: RMAN entra con `target /`.
- Cada programación se guarda en `SYSTEM.RESPALDOS_PROGRAMADOS` (se crea si no existe).
- En Linux o contenedor la ruta del DIRECTORY no puede llevar espacios, barra invertida ni caracteres de shell (`'` `"` `$` `` ` `` `;` `&` `|` `<` `>` `(` `)` `*` `?` `!` `%` `[` `]` `{` `}`); en Windows se admite el espacio simple, pero no los demás caracteres de esa lista. Si no cumple, se rechaza al programar.

### Limitaciones conocidas

- Las ejecuciones del cron no actualizan `ULTIMA_EJECUCION` ni `ULTIMO_RESULTADO` de la tabla: su resultado se ve en el `.log` de la lista de respaldos. Solo el botón Ejecutar los actualiza.
- `docker compose down` borra el crontab del contenedor: hay que pulsar «Reinstalar tareas». Los scripts sobreviven solo si el DIRECTORY está en el volumen `oracle_data`; si faltan, «Reinstalar tareas» los regenera.
- Tras un `docker restart` manual, `crond` no se arranca solo hasta que la app programe, elimine o reinstale una tarea (Ejecutar no lo arranca) o corras `levantar-oracle21c.*`.
- En cron, «Cada N horas» se reinicia a las 00:00 cada día; con un N que no divide 24 el último intervalo del día es más corto (en Windows, `schtasks` mantiene el intervalo exacto).
- Los scripts creados antes de la corrección del argumento `using` de RMAN (commit `92bba72`) y cuyo nombre llevaba guion (p. ej. `progra-full`) fallan con `RMAN-00552` / `RMAN-02001`. «Reinstalar tareas» solo regenera los scripts que faltan, no los desfasados: elimina esas programaciones desde la pantalla y vuelve a crearlas.
- Ejecutar bloquea la petición hasta que RMAN termina.
- Dos programaciones creadas a la vez con el mismo nombre pueden pisarse los scripts; se recupera con «Reinstalar tareas».
- En Windows, el diagnóstico de permisos al eliminar reconoce los mensajes de `schtasks` en español e inglés.
- No se editan ni se pausan programaciones (elimina y vuelve a crear).
- No se programan respaldos de tablas ni de schemas.

### Block Change Tracking (recomendado)

Para que los incrementales (nivel 1) lean solo los bloques cambiados, se recomienda activar Block Change Tracking. **La app no lo activa**; se hace a mano (guía: `docs/Politica_Rman_practica_win/Politica_Rman_practica_win.txt`):

```sql
sqlplus / as sysdba
SELECT STATUS, FILENAME FROM V$BLOCK_CHANGE_TRACKING;
ALTER DATABASE ENABLE BLOCK CHANGE TRACKING USING FILE '<ruta>/block_change_tracking.bct' REUSE;
SELECT STATUS, FILENAME, BYTES FROM V$BLOCK_CHANGE_TRACKING;
```

Después ejecuta un respaldo Full (nivel 0), que da el punto de partida limpio; a partir de ahí los incrementales aprovechan el mapa de cambios.

### Prueba de integración (NO ejecutada durante el desarrollo)

```bash
cd backend && uv run pytest -m integration tests/integration/test_respaldos_programados_oracle.py
```

**Esta prueba nunca se ha ejecutado contra una base real durante el desarrollo.** Requiere el contenedor `oracle21c` en marcha, `ORACLE_DATABASE_PASSWORD` y la base en ARCHIVELOG. Al ejecutarla:

- Crea `SYSTEM.RESPALDOS_PROGRAMADOS` (la borra al final solo si la creó ella y está vacía).
- Aplica la política global de RMAN (no se revierte).
- Instala y luego quita su línea del crontab del usuario `oracle` del contenedor.
- Crea y borra un DIRECTORY `PRUEBA_PROG_<hex>` y la carpeta `/tmp/prueba_prog_<hex>` dentro del contenedor.
- Arranca `crond` en el contenedor si no estaba corriendo (no lo detiene al final).
- Ejecuta `ALTER SYSTEM SWITCH LOGFILE` (forma parte del respaldo transaccional).
- Lanza un respaldo transaccional real.

> **Advertencia:** `BACKUP ARCHIVELOG ALL … DELETE INPUT` borra los archivelogs pendientes de la FRA, y la limpieza de la prueba borra después las piezas de ese respaldo. Esos archivelogs quedan perdidos si no existe otra copia. Ejecútala solo en una base de pruebas o después de respaldar los archivelogs pendientes.

## Comandos útiles

```bash
docker logs -f oracle21c        # ver logs
docker compose stop             # detener el contenedor
docker compose start            # volver a iniciarlo
docker compose down             # eliminar el contenedor (los datos se conservan)
docker compose down -v          # eliminar contenedor Y datos (volumen oracle_data)
```

Los datos se guardan en el volumen Docker `oracle_data`, por lo que persisten entre reinicios.
