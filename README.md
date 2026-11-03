# Методические указания по выполнению лабораторной работы №4
## FastAPI (Python, FastAPI, SQLAlchemy, Jinja2, куки + Redis)

Веб-сервис «Wi-Fi Routers» — каталог Wi-Fi оборудования. В лабораторной работе №4 к бэкенду добавляются:

- **Регистрация и аутентификация через куки (сессии)**,
- **Модель доступа**: гость — только чтение, создатель — свои услуги (401 / 403),
- **Автоматическое привязывание пользователя к его услугам** (поле `creator` из сессии вместо константы),
- **Хранение активных сессий в Redis**,
- **HTML-страницы на Jinja2** с пользователем из сессии,
- **Swagger-документация для тестирования JSON API**.

---

# Содержание

- [Чем отличается аутентификация от авторизации?](#чем-отличается-аутентификация-от-авторизации)
- [Куки и сессии: теория и принцип работы](#куки-и-сессии-теория-и-принцип-работы)
- [Зачем нужен Redis при использовании сессий?](#зачем-нужен-redis-при-использовании-сессий)
- [Подготовка окружения](#подготовка-окружения)
- [Структура проекта FastAPI](#структура-проекта-fastapi)
- [Настройка FastAPI и Swagger](#настройка-fastapi-и-swagger)
- [Реализация моделей Users и Router](#реализация-моделей-users-и-router)
- [Аутентификация: сессии, зависимости, контроллер](#аутентификация-сессии-зависимости-контроллер)
- [Контроллеры с авторизацией](#контроллеры-с-авторизацией)
- [Настройка Jinja2](#настройка-jinja2)
- [Тестирование](#тестирование)
- [Порядок показа](#порядок-показа)
- [Контрольные вопросы](#контрольные-вопросы)
- [Заключение](#заключение)

---

## Чем отличается аутентификация от авторизации?

- **Аутентификация** — подтверждение личности: *«Кто ты?»*
  Пример: ввод логина и пароля → сервер проверяет их в таблице `users` и выдаёт сессию.

- **Авторизация** — проверка прав: *«Что ты можешь?»*
  Пример: гость может только читать список и ленту; создатель может публиковать и удалять **только свои** услуги — чужая даёт 403.

В коде это две разные зависимости: `require_user` (аутентификация, 401) и `ensure_owner` (авторизация, 403).

---

## Куки и сессии: теория и принцип работы

В отличие от JWT, **сессионная аутентификация — stateful**: сервер хранит информацию о сессии (у нас — в Redis).

**Как это работает**:

1. При `POST /api/login` сервер проверяет логин и пароль.
2. Если данные верны — создаёт запись в Redis:
   ```text
   session:6099e7c01da54dcebd367d64455dfe2c → {"id_user": 13, "username": "user_0"}
   ```
3. Устанавливает куку:
   ```http
   Set-Cookie: sessionId=6099e7c01da54dcebd367d64455dfe2c; HttpOnly; Max-Age=3600; Path=/; SameSite=lax
   ```
4. Браузер автоматически отправляет эту куку при каждом запросе (в Postman/Insomnia — заголовок `Cookie: sessionId=...`).
5. Сервер читает `sessionId`, ищет сессию в Redis → если найдена, пользователь авторизован.

> 🔑 Кука с флагом `HttpOnly` недоступна из JavaScript → защита от XSS.

> 💡 При logout сессия удаляется из Redis → мгновенная деавторизация.

---

## Зачем нужен Redis при использовании сессий?

Сессии должны храниться внешне (не в памяти процесса), чтобы:

- работать в кластере (несколько экземпляров uvicorn),
- сохранять сессии после перезапуска сервера,
- быстро проверять и удалять сессии (TTL = 1 час).

Redis — идеальное решение: быстрое, простое, надёжное. Ещё один плюс — содержимое сессий видно через `redis-cli`.

---

## Подготовка окружения

Убедитесь, что установлены:

- **Python 3.13**
  ```bash
  python --version  # ≥ 3.13
  ```

- **Docker** (для PostgreSQL, MinIO и Redis)
  ```bash
  docker --version
  ```

В `docker-compose.yml` к PostgreSQL, MinIO и Adminer добавлен Redis:

```yaml
  redis:
    image: redis:7-alpine
    container_name: redis_session
    ports:
      - "6379:6379"
```

Запуск:

```bash
docker compose up -d
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

Настройки в `.env` (читаются в `core/config.py` через `pydantic-settings`):

```dotenv
DB_HOST=localhost
DB_PORT=5433
DB_USER=...
DB_PASSWORD=...
DB_NAME=routers_db

MINIO_ENDPOINT=localhost
MINIO_PORT=9000
MINIO_BUCKET=wifi-routers

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
SESSION_TTL=3600
```

---

## Структура проекта FastAPI

Для сессий понадобилась одна новая зависимость — `redis==8.1.0` (асинхронный клиент `redis.asyncio`).

```text
wifi-equipment/
├── main.py               # приложение FastAPI, Swagger, подключение роутеров
├── core/
│   ├── config.py         # настройки из .env
│   └── session.py        # хранилище сессий в Redis          (новое)
├── db/                   # движок SQLAlchemy (async), Base
├── models/               # Users, Router, Likes
├── api/
│   ├── deps.py           # зависимости: текущий пользователь, права (переписано)
│   ├── user.py           # домен пользователя: register / login / logout
│   ├── routers.py        # домен услуги: JSON API
│   ├── schemas.py        # Pydantic-модели ответов для Swagger   (новое)
│   ├── serializers.py    # модель → dict
│   └── handlers.py       # HTML-страницы на Jinja2
├── templates/            # tape, tile, add (.html)
├── minio_client.py       # загрузка картинок и видео в MinIO
└── alembic/              # миграции БД
```

---

## Настройка FastAPI и Swagger

В `main.py` подключаются роутеры и описание API для Swagger. Swagger доступен по адресу <http://127.0.0.1:8000/docs>.

```python
DESCRIPTION = """
REST API каталога Wi-Fi оборудования с **сессионной аутентификацией через куку**.

### Правила доступа
* **Без авторизации** — только чтение: `GET /api/routers`, `GET /api/router`.
  Работает независимо от токена/куки.
* **С авторизацией** — методы создателя: создание черновика, публикация, удаление,
  лайк, получение черновика. Без куки — **401**, для чужой услуги — **403**.
...
"""

app = FastAPI(
    title="Wi-Fi Routers API",
    description=DESCRIPTION,
    version="4.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)           # HTML-страницы (в Swagger не показываются)
app.include_router(routers_router)   # /api/routers, /api/router...
app.include_router(user_router)      # /api/register, /api/login, /api/logout
```

Кнопка **Authorize** появляется автоматически: зависимость `require_user` объявлена через `APIKeyCookie` (см. ниже), и FastAPI добавляет в OpenAPI схему безопасности с кукой `sessionId`. У методов создателя в Swagger появляется замок.

---

## Реализация моделей Users и Router

Модели SQLAlchemy уже были созданы в лабораторных 2–3. Для лабораторной 4 важно, что у услуги есть поле `creator` — теперь оно заполняется из сессии.

`models/users.py`:
```python
class Users(Base):
    __tablename__ = "users"

    id_user = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
```

`models/routers.py`:
```python
class Router(Base):
    __tablename__ = "routers"

    id_routers = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    standard = Column(String(50), nullable=True)
    max_speed = Column(Integer, nullable=True)
    band = Column(String(20), nullable=True)
    antennas = Column(String(30), nullable=True)
    frequency = Column(Float, nullable=True)
    image_url = Column(String(255), nullable=True)
    video_url = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    date_created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    creator = Column(String(50), nullable=False)        # ← username из сессии
    date_formed = Column(TIMESTAMP, nullable=True)
    date_completed = Column(TIMESTAMP, nullable=True)
    status = Column(String(20), nullable=False, server_default="черновик")
```

`models/likes.py`:
```python
class Likes(Base):
    __tablename__ = "likes"

    id_user = Column(Integer, ForeignKey("users.id_user"), nullable=False, primary_key=True)
    id_routers = Column(Integer, ForeignKey("routers.id_routers"), nullable=False, primary_key=True)
```

Pydantic-модели ответов для Swagger — `api/schemas.py`:
```python
class UserSchema(BaseModel):
    id_user: int = Field(description="Идентификатор пользователя")
    username: str = Field(description="Логин")


class AuthResponseSchema(BaseModel):
    user: UserSchema = Field(description="Аутентифицированный пользователь")


class RouterSchema(BaseModel):
    id_routers: int = Field(description="Идентификатор услуги")
    title: str = Field(description="Название")
    ...
    creator: str = Field(description="Логин создателя (заполняется из сессии)")
```

---

## Аутентификация: сессии, зависимости, контроллер

В этой реализации используется сессионная аутентификация через куки. Сервер хранит активные сессии в Redis, а клиент получает куку `sessionId`.

### Хранилище сессий — `core/session.py`

```python
import json
import uuid

from redis.asyncio import Redis

from core.config import settings

redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


async def create_session(user_id: int, username: str) -> str:
    session_id = uuid.uuid4().hex
    payload = json.dumps({"id_user": user_id, "username": username}, ensure_ascii=False)
    await redis_client.setex(f"session:{session_id}", settings.SESSION_TTL, payload)
    return session_id


async def get_session(session_id: str) -> dict | None:
    raw = await redis_client.get(f"session:{session_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def destroy_session(session_id: str) -> None:
    await redis_client.delete(f"session:{session_id}")
```

Ключ — `session:<uuid>`, значение — JSON с пользователем, TTL — `SESSION_TTL` (1 час).

### Зависимости вместо guard — `api/deps.py`

В FastAPI роль guard'а из NestJS выполняют зависимости (`Depends`). Константа-синглтон из лабораторной 3 (`USER_ID = 1`) заменена на пользователя из сессии:

```python
COOKIE_NAME = "sessionId"

cookie_scheme = APIKeyCookie(
    name=COOKIE_NAME,
    description="Сессионная кука (HttpOnly), выдаваемая в Set-Cookie при POST /api/login. ...",
    auto_error=False,
)


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Users | None:
    """Для открытых GET: без куки — гость (None), признаки is_creator/is_liked = 0."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        return None
    session = await get_session(session_id)
    if session is None:
        return None
    return await _load_user(db, session["id_user"])


async def require_user(
    session_id: str | None = Depends(cookie_scheme),
    db: AsyncSession = Depends(get_db),
) -> Users:
    """Для методов создателя: нет куки или сессия истекла — 401."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Требуется аутентификация: нет куки sessionId")
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Сессия недействительна или истекла")
    user = await _load_user(db, session["id_user"])
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь сессии не найден")
    return user


def ensure_owner(user: Users, router_creator: str) -> None:
    """Авторизация: операции с услугой — только её создателю."""
    if user.username != router_creator:
        raise HTTPException(status_code=403, detail="Недостаточно прав: услуга принадлежит другому пользователю")
```

> 💡 `require_user` проверяет куку `sessionId`, ищет сессию в Redis и возвращает пользователя из БД — так же, как `SessionGuard` в NestJS кладёт `userId` в `req.session`.

### Контроллер пользователя — `api/user.py`

Регистрация и вход принимают `form-data` (`username`, `password`):

```python
router = APIRouter(prefix="/api", tags=["Пользователь"])


@router.post("/register", response_model=UserSchema, summary="Регистрация пользователя",
             responses={409: {"description": "Логин уже занят"}})
async def register(
    username: str = Form(..., description="Логин (уникальный)"),
    password: str = Form(..., description="Пароль"),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Users).where(Users.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")

    user = Users(username=username, password=password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id_user": user.id_user, "username": user.username}


@router.post("/login", response_model=AuthResponseSchema, summary="Аутентификация (выдача сессии)")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Users).where(Users.username == username))
    user = result.scalar_one_or_none()
    if user is None or user.password != password:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    session_id = await create_session(user.id_user, user.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_TTL,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"user": {"id_user": user.id_user, "username": user.username}}


@router.post("/logout", summary="Деавторизация (уничтожение сессии)")
async def logout(
    response: Response,
    user: Users = Depends(require_user),
    session_id: str | None = Depends(cookie_scheme),
):
    await destroy_session(session_id)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}
```

---

## Контроллеры с авторизацией

`api/routers.py` — домен услуги. Открытые методы получают `Depends(get_optional_user)`, методы создателя — `Depends(require_user)`:

Всего **10 методов**: 7 в домене «Услуги» и 3 в домене «Пользователь».

| № | Метод | URL | Назначение | Доступ | Коды ответа |
|---|---|---|---|---|---|
| 1 | GET | `/api/routers?freq_min=&freq_max=` | список опубликованных с фильтром, `is_creator` 0/1 | гость и создатель | 200 |
| 2 | GET | `/api/router?id_routers=&next=` | лента опубликованных: без `id_routers` — первая, с `id_routers` — указанная, `next=true` — следующая по кругу; `like_count`, `is_liked` 0/1 | гость и создатель | 200 / 404 |
| 3 | GET | `/api/router/draft` | черновик текущего пользователя (не более одного), ид не передаётся | создатель | 200 (черновик или `null`) / 401 |
| 4 | POST | `/api/router` | добавление: `title`, файлы `image` и `video` → MinIO, в БД — латинские имена `uuid.ext` | создатель | 200 / 401 / 409 (уже есть черновик) |
| 5 | PUT | `/api/router/{id_routers}` | публикация (черновик → опубликован) | создатель | 200 / 401 / 403 (чужая) / 404 / 409 (не черновик) |
| 6 | DELETE | `/api/router/{id_routers}` | soft delete, только свои | создатель | 200 / 401 / 403 / 404 |
| 7 | POST | `/api/router/{id_routers}` | лайк: `like=1` — поставить, `like=0` — отменить | создатель | 200 / 401 / 404 (нет или не опубликована) / 422 (`like` не 0/1) |
| 8 | POST | `/api/register` | регистрация | гость | 200 / 409 |
| 9 | POST | `/api/login` | аутентификация | гость | 200 + `Set-Cookie` / 401 |
| 10 | POST | `/api/logout` | деавторизация | создатель | 200 / 401 |

Создание услуги — автор берётся из сессии:

```python
@router.post("/router", response_model=RouterSchema, summary="Создать черновик услуги (с картинкой и видео)",
             responses={**OWNER_ONLY, 409: {"description": "У пользователя уже есть черновик"}})
async def create_router(
    title: str = Form(..., description="Название услуги"),
    image: UploadFile = File(..., description="Изображение (jpg/png)"),
    video: UploadFile = File(..., description="Видео (mp4)"),
    user: Users = Depends(require_user),          # ← вместо константы USER_ID = 1
    db: AsyncSession = Depends(get_db),
):
    ...
    image_url = upload_file(await image.read(), image.filename)
    video_url = upload_file(await video.read(), video.filename)

    item = Router(
        title=title,
        image_url=image_url,
        video_url=video_url,
        status=DRAFT,
        date_created=datetime.now(),
        creator=user.username,                    # ← автор из сессии
    )
```

Публикация — проверка прав:

```python
@router.put("/router/{id_routers}", response_model=RouterSchema, summary="Опубликовать услугу (черновик → опубликован)")
async def publish_router(
    id_routers: int,
    description: str = Form(...),
    frequency: float = Form(...),
    ...,
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    item = (await db.execute(select(Router).where(Router.id_routers == id_routers))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    ensure_owner(user, item.creator)              # ← чужая услуга → 403
    if item.status != DRAFT:
        raise HTTPException(status_code=409, detail="Публикация возможна только из статуса «черновик»")
    ...
    item.status = PUBLISHED
    item.date_formed = datetime.now()
```

В открытых методах признаки считаются для текущего пользователя, у гостя они всегда 0:

```python
"is_creator": 1 if (user is not None and e.creator == user.username) else 0
"is_liked": 1 if is_liked else 0
```

---

## Настройка Jinja2

HTML-страницы из лабораторных 1–2 (`/feed`, `/grid`, `/add`) остаются для демонстрации и в Swagger не попадают (`APIRouter(include_in_schema=False)`). Отдельной HTML-страницы входа нет, поэтому пользователь на них определяется так: если в браузере есть кука `sessionId` (вход через `POST /api/login` в Swagger), это пользователь сессии, иначе — пользователь по умолчанию `user_0`. JSON API (`/api/...`) работает строго по сессии.

`api/handlers.py`:

```python
DEFAULT_HTML_USER = "user_0"


async def get_html_user(
    user: Users | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Users:
    if user is not None:
        return user
    result = await db.execute(select(Users).where(Users.username == DEFAULT_HTML_USER))
    return result.scalar_one()


@router.post("/add")
async def add_draft(
    title: str = Form(...),
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    user: Users = Depends(get_html_user),
    db: AsyncSession = Depends(get_db),
):
    existing_draft = await get_draft(user.username, db)
    if existing_draft is None:
        new_router = Router(
            title=title,
            image_url=upload_file(await image.read(), image.filename),   # файл → MinIO
            video_url=upload_file(await video.read(), video.filename),
            creator=user.username,
            status="черновик",
            date_created=datetime.now(),
        )
        ...
```

Форма добавления отправляет файлы, поэтому у неё `enctype="multipart/form-data"`, а у полей файлов — `name`:

```html
<form class="add-form" method="post" action="/add" enctype="multipart/form-data">
    <input type="file" name="image" accept="image/*" required>
    <input type="file" name="video" accept="video/*" required>
    <input type="text" name="title" required>
    ...
</form>
```

В БД хранится только имя файла, поэтому в шаблонах адрес строится фильтром `media` (это функция `file_url` из `minio_client.py`):

```html
{% set img_src = (router.image_url | media) if router.image_url else '/static/img/default.svg' %}
```

Удаление на странице плитки (`POST /routers/{id}/delete`, SQL `UPDATE` из лабораторной 2) теперь удаляет только свои услуги (`WHERE id_routers = :id AND creator = :creator`). Кнопка «Удалить» показывается только на своих карточках.

---

## Тестирование

### 1. Swagger

Откройте <http://127.0.0.1:8000/docs> **в режиме инкогнито**, чтобы начать без старых кук.

- **Регистрация** — `POST /api/register`, form-data: `username`, `password`. Ответ 200:
  ```json
  { "id_user": 31, "username": "student" }
  ```
  Если логин занят — 409.
- **Логин** — `POST /api/login`, те же поля. Ответ 200:
  ```json
  { "user": { "id_user": 31, "username": "student" } }
  ```
  В заголовках ответа — `Set-Cookie: sessionId=...; HttpOnly`. Браузер сохранит куку, и запросы из этой вкладки уже авторизованы. Значение куки видно в DevTools → **Application → Cookies → http://127.0.0.1:8000**.
- **Список услуг** — `GET /api/routers` → 200.
- Вместо куки браузера можно нажать **Authorize** и вставить значение `sessionId`.

### 2. Postman / Insomnia

Скопируйте значение `sessionId` из вкладки **Application** и передавайте его в запросах создателя заголовком:

```http
Cookie: sessionId=6099e7c01da54dcebd367d64455dfe2c
```

(В Postman это можно сделать и через вкладку **Cookies** под кнопкой Send.)

- `GET /api/routers?freq_min=2.4&freq_max=6` **без куки** → 200, работает независимо от куки.
- `GET /api/router` и `GET /api/router?id_routers=1&next=true` без куки → 200.
- `PUT /api/router/{id}` **без куки** → 401:
  ```json
  { "detail": "Требуется аутентификация: нет куки sessionId" }
  ```
- `PUT /api/router/{id}` с кукой, **чужая** услуга → 403.
- `PUT /api/router/{id}` с кукой, свой черновик, form-data `description`, `frequency`, `standard`, `max_speed`, `antennas` → 200, поля обновлены, `status: "опубликован"`, заполнена `date_formed`.
- `POST /api/router` с кукой → в ответе `creator` = ваш логин (автор подставился из сессии).
- `POST /api/logout` → `{ "ok": true }`. Повторный запрос с той же кукой → 401: сессия удалена.

### 3. Redis через cmd

```bat
docker exec redis_session redis-cli KEYS "session:*"
docker exec redis_session redis-cli GET "session:6099e7c01da54dcebd367d64455dfe2c"
docker exec redis_session redis-cli TTL "session:6099e7c01da54dcebd367d64455dfe2c"
```

```text
1) "session:6099e7c01da54dcebd367d64455dfe2c"
{"id_user": 31, "username": "student"}
(integer) 3016
```

В значении сессии виден пользователь. После logout `GET` возвращает `(nil)`.

### 4. Jinja2 через браузер

Откройте <http://127.0.0.1:8000/add>: выберите фото и видео, введите название и нажмите «Далее» — файлы загрузятся в MinIO, появится черновик с превью. Заполните частоту и описание и нажмите «Опубликовать» — откроется лента с новой услугой. Без входа черновик создаётся от `user_0`; после `POST /api/login` в Swagger в той же вкладке — от вашего пользователя.

---

## Порядок показа

| № | Что показать |
|---|---|
| 1–3 | Swagger в режиме инкогнито: `POST /api/login` → 200 и `Set-Cookie`; кука во вкладке Application; `GET /api/routers` → 200 |
| 4–5 | Postman/Insomnia: `GET /api/routers` и `GET /api/router` без куки → 200 |
| 6–8 | `PUT /api/router/{id}`: без куки → 401, чужая услуга → 403, с кукой → 200 и обновлённые поля; содержимое Redis через cmd (`KEYS`, `GET` — в сессии виден пользователь) |
| 9 | StarUML: у сообщений диаграммы последовательности свойство `signature` выбрано из методов доменов диаграммы классов |

Диаграмма последовательности: Lifeline — «Фронтенд (пользователь)», «Домен Пользователь», «Домен Роутер». Сообщения: аутентификация → список с фильтром → добавление с картинкой и видео → черновик → публикация → лента без ид → лента по ид `?next=true` → лайк. В `arguments` — ключевые входные и выходные данные (`username, password`; `sessionId`; `title, image, video`; `id_routers` и т. д.).

---

## Контрольные вопросы

**Куки** — пары «имя=значение», которые сервер присылает в заголовке `Set-Cookie`, а браузер возвращает в заголовке `Cookie`. `HttpOnly` запрещает доступ из JavaScript, `SameSite=Lax` снижает риск CSRF, `Max-Age` задаёт время жизни.

**Сессия** — состояние «пользователь вошёл», которое хранит сервер. В куке лежит только идентификатор сессии, данные — в Redis. Выход и истечение TTL срабатывают сразу.

**Redis** — быстрое хранилище «ключ-значение» в памяти с TTL. Хранит `session:<id> → пользователь`, переживает перезапуск приложения и общий для нескольких экземпляров сервиса.

**JWT** — подписанный токен `header.payload.signature`, передаётся в заголовке `Authorization: Bearer`. Сервер не хранит его, поэтому для выхода нужен чёрный список отозванных токенов (blacklist, обычно в Redis). По заданию JWT используется в варианте на Golang, а для FastAPI — сессии и куки.

**Аутентификация и авторизация** — «кто ты?» (проверка логина и пароля, выдача сессии) и «что тебе можно?» (401 без сессии, 403 для чужой услуги).

**SSO** — единый вход: одна аутентификация даёт доступ к нескольким сервисам (OAuth 2.0 / OpenID Connect, SAML, Kerberos).

**Двухфакторная аутентификация** — кроме пароля нужен второй фактор: код из SMS или приложения (TOTP), аппаратный ключ. Украденного пароля недостаточно для входа.

**RSA** — асимметричный алгоритм с парой ключей. Открытым ключом шифруют и проверяют подпись, закрытым — расшифровывают и подписывают. Используется в TLS/HTTPS, SSH и для подписи JWT (RS256).

---

## Заключение

Вы реализовали:

  ✅ сессионную аутентификацию через HttpOnly-куку `sessionId`,
  ✅ хранение данных в PostgreSQL (SQLAlchemy),
  ✅ хранение сессий в Redis,
  ✅ HTML-страницы на Jinja2 с пользователем из сессии,
  ✅ JSON API с тестированием в Swagger,
  ✅ модель доступа «гость — чтение, создатель — свои услуги» и автоматическое заполнение `creator`.

### Полезные ссылки

- [FastAPI — Security](https://fastapi.tiangolo.com/tutorial/security/)
- [FastAPI — Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI — Response Cookies](https://fastapi.tiangolo.com/advanced/response-cookies/)
- [redis-py (asyncio)](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [OWASP: Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Методические указания Redis](https://github.com/iu5git/Web/blob/main/tutorials/redis/README.md)
