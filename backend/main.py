from fastapi import FastAPI

from src.api.respaldos import router as respaldos_router

app = FastAPI()
app.include_router(respaldos_router)


@app.get("/")
def read_root():
  return {"Hello": "World"}
