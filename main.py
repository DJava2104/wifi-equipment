from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routers import router as routers_router
from api.handlers import router
from api.user import router as user_router
from minio_client import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="Wi-Fi Speed Calculator", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
app.include_router(routers_router)
app.include_router(user_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
