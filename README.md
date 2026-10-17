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

## Comandos útiles

```bash
docker logs -f oracle21c        # ver logs
docker compose stop             # detener el contenedor
docker compose start            # volver a iniciarlo
docker compose down             # eliminar el contenedor (los datos se conservan)
docker compose down -v          # eliminar contenedor Y datos (volumen oracle_data)
```

Los datos se guardan en el volumen Docker `oracle_data`, por lo que persisten entre reinicios.
