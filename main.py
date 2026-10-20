from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.equipment import router as equipment_router
from api.handlers import router
from api.user import router as user_router
from minio_client import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield


DESCRIPTION = """
REST API каталога Wi-Fi оборудования с **сессионной аутентификацией через куку**.

### Правила доступа
* **Без авторизации** — только чтение: `GET /api/equipments`, `GET /api/equipment`,
  `GET /api/equipment/{id}`. Работает независимо от токена/куки.
* **С авторизацией** — методы создателя: создание черновика, публикация, удаление,
  лайк, получение черновика. Без куки — **401**, для чужой услуги — **403**.

### Как получить куку
1. `POST /api/register` — регистрация (form-data: `username`, `password`).
2. `POST /api/login` — в ответе заголовок `Set-Cookie: sessionId=...; HttpOnly`.
   Сессия сохраняется в Redis: `session:<id>` → `{"id_user": ..., "username": ...}`.
3. В Swagger эта же вкладка браузера пришлёт куку автоматически.
   В Postman/Insomnia вставьте заголовок `Cookie: sessionId=<значение>`.
4. `POST /api/logout` — удаляет сессию из Redis (мгновенная деавторизация).
"""

app = FastAPI(
    title="Wi-Fi Equipment API",
    description=DESCRIPTION,
    version="4.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
app.include_router(equipment_router)
app.include_router(user_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
