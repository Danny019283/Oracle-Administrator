from fastapi import FastAPI

from src.api.respaldos import router as respaldos_router
from src.api.sesion import router as sesion_router

app = FastAPI()
app.include_router(respaldos_router)
app.include_router(sesion_router)


@app.get("/")
def read_root():
  return {"Hello": "World"}
