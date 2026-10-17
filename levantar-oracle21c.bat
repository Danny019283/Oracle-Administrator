@echo off
cd /d "%~dp0"

docker compose up -d
if errorlevel 1 (
    echo Error al levantar el contenedor.
    exit /b 1
)

echo Esperando a que Oracle este listo (puede tardar varios minutos)...

set /a intentos=0

:esperar
docker logs oracle21c 2>&1 | findstr /C:"DATABASE IS READY TO USE" >nul
if not errorlevel 1 goto listo

set /a intentos+=1
if %intentos% geq 120 (
    echo Tiempo agotado. Revisa: docker logs oracle21c
    exit /b 1
)

timeout /t 5 /nobreak >nul
goto esperar

:listo
echo Oracle listo en localhost:1521
