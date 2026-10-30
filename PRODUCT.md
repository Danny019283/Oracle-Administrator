# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Un DBA o estudiante de bases de datos que administra su propia instancia de Oracle Database 21c XE, levantada en Docker en su equipo local. Su trabajo es ejecutar tareas de administración (hoy, respaldos con Data Pump) sin memorizar la sintaxis de los comandos. Por ahora es un único usuario local: la autenticación propia de la aplicación aún no existe.

## Product Purpose

Administrador Oracle convierte tareas de administración de Oracle en flujos visuales guiados. Hoy permite respaldar tablas con `expdp` (elegir tablas, DIRECTORY y nombre del dumpfile). El éxito es que el administrador complete una tarea sin escribir comandos y, cuando algo falla, entienda exactamente qué ocurrió.

El alcance de producto previsto, de los requisitos del autor: administración de tablespaces, tuning de consultas (planes de ejecución, estadísticas, índices), performance de la base de datos, auditoría de la BD, seguridad de usuarios, creación de respaldos (por tablas, schemas o full), recuperación de respaldos y administración de archivos de respaldos y directorios. Están construidos el respaldo de tablas y la recuperación de respaldos.

## Positioning

Guiado y sin escribir comandos: cada tarea es un flujo paso a paso y los errores de Oracle se explican en lenguaje natural, conservando el código ORA y el log.

## Operating Context

Se usa en local, junto a un contenedor Docker `oracle21c` (Oracle XE 21c, servicio `XEPDB1`). El backend ejecuta `expdp` dentro del contenedor y guarda los respaldos (`.dmp` y `.log`) en un DIRECTORY de Oracle. Frontend en React con Vite; backend en FastAPI.

## Capabilities and Constraints

- Construido: menú principal, submenú de respaldos, respaldo de tablas (listar tablas del usuario conectado, listar DIRECTORY con READ y WRITE, nombre de dumpfile con fecha y hora, explicación de errores ORA, aviso de backend caído).
- Construido: recuperación de respaldos. Desde un respaldo Data Pump se recuperan tablas y schemas con `impdp` (sesión SYSDBA o DBA); desde un respaldo full RMAN, la base completa con RESTORE/RECOVER, SHUTDOWN y cierre de sesiones (sesión SYSDBA), o una sola tabla con RECOVER TABLE, con REMAP y UNTIL TIME (sesión SYSDBA; no funciona en Oracle Express Edition, donde la instancia auxiliar choca con la restricción de instancia única). Cada recuperación deja un log `<base>_recuperacion_AAAAMMDD-HHMMSS.log` junto al respaldo.
- Pendiente de construir: respaldo de schemas, respaldo de base completa, creación de DIRECTORY y el resto de módulos del menú.
- Las credenciales de Oracle se ingresan una vez al abrir la app y viven solo en memoria de la sesión; esa pantalla de ingreso aún no existe.
- Interfaz solo en español.
- Las acciones destructivas (recuperaciones con `impdp`, `DROP USER`, sobrescrituras) deben pedir confirmación explícita.
- Nunca se muestran contraseñas: ni en pantalla, ni en logs, ni en mensajes de error.

## Brand Commitments

- Nombre del producto: Administrador Oracle.
- Debe ofrecer tema claro y oscuro.
- Estética pedida por el autor: minimalismo y claridad tipo Google (espacios en blanco amplios, jerarquía visual directa, tipografías legibles) combinado con neumorfismo / Soft UI (elementos planos con sombras suaves que dan un efecto táctil y flotante a botones y tarjetas). Esta elección sustituye a la dirección sorteada «Elevación de rack».

## Evidence on Hand

No hay contenido real de marca, capturas, testimonios ni datos. No se debe inventar ninguno.

## Product Principles

1. Guiar antes que exponer: cada tarea es un flujo con pasos claros, no una consola de comandos.
2. Explicar los errores: toda falla muestra qué ocurrió en lenguaje natural, sin esconder el código ORA ni el log.
3. Proteger al administrador: confirmar lo destructivo y nunca revelar secretos.
4. Una pantalla a la vez, con un camino claro de ida y de vuelta.

## Accessibility & Inclusion

Tema claro y oscuro. No se estableció un estándar de accesibilidad concreto; está abierto. Hoy los avisos de éxito y de error ya usan las regiones `status` y `alert`.
