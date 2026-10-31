import os
import sys

from fastapi import FastAPI

from src.api.auditoria import router as auditoria_router
from src.api.dependencias import fijar_entorno
from src.api.directorios import router as directorios_router
from src.api.estado_base import router as estado_base_router
from src.api.performance import router as performance_router
from src.api.respaldos import router as respaldos_router
from src.api.seguridad import router as seguridad_router
from src.api.sesion import router as sesion_router
from src.api.tablespaces import router as tablespaces_router
from src.api.tuning import router as tuning_router
from src.services.entorno_fabrica import fabrica_desde_variables

# Con un valor inválido la carga falla aquí, antes de crear la aplicación
entorno = fabrica_desde_variables(os.environ, sys.platform)
fijar_entorno(entorno)

app = FastAPI()
app.include_router(respaldos_router)
app.include_router(sesion_router)
app.include_router(performance_router)
app.include_router(auditoria_router)
app.include_router(seguridad_router)
app.include_router(tablespaces_router)
app.include_router(tuning_router)
app.include_router(directorios_router)
app.include_router(estado_base_router)


@app.get("/")
def read_root():
  return {"Hello": "World"}
