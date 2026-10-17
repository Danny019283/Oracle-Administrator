@echo off
cd /d "%~dp0"

docker compose pull
if errorlevel 1 (
    echo Error al descargar la imagen.
    exit /b 1
)
echo Imagen descargada.
