from fastapi import FastAPI

from src.api.auditoria import router as auditoria_router
from src.api.performance import router as performance_router
from src.api.respaldos import router as respaldos_router
from src.api.seguridad import router as seguridad_router
from src.api.tablespaces import router as tablespaces_router

app = FastAPI()
app.include_router(respaldos_router)
app.include_router(performance_router)
app.include_router(auditoria_router)
app.include_router(seguridad_router)
app.include_router(tablespaces_router)


@app.get("/")
def read_root():
  return {"Hello": "World"}
