from fastapi import FastAPI

from src.api.auditoria import router as auditoria_router
from src.api.performance import router as performance_router
from src.api.respaldos import router as respaldos_router
from src.api.seguridad import router as seguridad_router
from src.api.sesion import router as sesion_router

app = FastAPI()
app.include_router(respaldos_router)
app.include_router(sesion_router)
app.include_router(performance_router)
app.include_router(auditoria_router)
app.include_router(seguridad_router)


@app.get("/")
def read_root():
  return {"Hello": "World"}
