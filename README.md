# Методические указания по выполнению лабораторной работы №4
## FastAPI (Python, FastAPI, SQLAlchemy async, Jinja2, куки + Redis, Swagger)

Веб-сервис «Wi-Fi Equipment» — REST API каталога Wi-Fi оборудования. В лабораторной работе №4 бэкенд дополняется:

- **Регистрацией и аутентификацией через куки (сессии в Redis)**,
- **Моделями доступа**: без авторизации — только чтение (GET), с авторизацией — методы создателя,
- **Автозаполнением создателя** в таблице `equipment` из текущей сессии (вместо константы),
- **Swagger-документацией** с cookie-авторизацией (Authorize),
- **Postman-коллекцией** с заголовком `Cookie` и проверками 401/403.

---

# Содержание

- [Чем отличается аутентификация от авторизации?](#чем-отличается-аутентификация-от-авторизации)
- [Куки и сессии: теория и принцип работы](#куки-и-сессии-теория-и-принцип-работы)
- [Зачем нужен Redis при использовании сессий?](#зачем-нужен-redis-при-использовании-сессий)
- [Подготовка окружения](#подготовка-окружения)
- [Что изменилось в проекте](#что-изменилось-в-проекте)
- [Session store: работа с Redis](#session-store-работа-с-redis)
- [Зависимости (guard'ы): текущий пользователь и права](#зависимости-guardы-текущий-пользователь-и-права)
- [Домен пользователя: register / login / logout](#домен-пользователя-register--login--logout)
- [Домен услуги: guard'ы, автозаполнение creator, статусы](#домен-услуги-guardы-автозаполнение-creator-статусы)
- [Swagger: описание методов и Authorize](#swagger-описание-методов-и-authorize)
- [Тестирование](#тестирование)
- [Порядок показа и скриншоты](#порядок-показа-и-скриншоты)
- [Контрольные вопросы](#контрольные-вопросы)
- [Заключение](#заключение)

---

## Чем отличается аутентификация от авторизации?

- **Аутентификация** — подтверждение личности: *«Кто ты?»*
  Пример: ввод username и пароля → сервер проверяет их в таблице `users` и выдаёт сессию.

- **Авторизация** — проверка прав: *«Что ты можешь?»*
  Пример: без куки — только GET-чтение (401 для остального); с кукой — методы создателя, но со своей услугой, а не с чужой (403).

---

## Куки и сессии: теория и принцип работы

В отличие от JWT, **сессионная аутентификация — stateful**: сервер хранит информацию о сессии (в Redis).

**Как это работает в нашем сервисе**:

1. `POST /api/register` — создаётся запись в `users` (логин уникален, иначе 409).
2. `POST /api/login` — сервер проверяет username/пароль. Если данные верны, создаёт запись в Redis:
   ```text
   session:6099e7c01da54dcebd367d64455dfe2c → {"id_user": 13, "username": "stuba33a4a5"}
   ```
3. Устанавливается HttpOnly-кука:
   ```http
   Set-Cookie: sessionId=6099e7c01da54dcebd367d64455dfe2c; HttpOnly; Max-Age=3600; Path=/; SameSite=lax
   ```
4. Браузер (и Swagger в той же вкладке) автоматически отправляет куку при каждом запросе.
5. В Postman/Insomnia куку передаём вручную заголовком:
   ```http
   Cookie: sessionId=6099e7c01da54dcebd367d64455dfe2c
   ```
6. Сервер читает `sessionId`, ищет сессию в Redis → если найдена, достаёт пользователя из БД и пускает в «методы создателя».
7. `POST /api/logout` — сессия удаляется из Redis → **мгновенная деавторизация** (та же кука сразу даёт 401).

> Кука с флагом `HttpOnly` недоступна из JavaScript → защита от XSS.

---

## Зачем нужен Redis при использовании сессий?

Сессии должны храниться внешне (не в памяти процесса), чтобы:

- работать в кластере (несколько экземплялов приложения),
- сохранять сессии после перезапуска сервера,
- быстро проверять и удалять сессии (TTL = 1 час), а также смотреть их из `redis-cli` во время отладки.

Redis — идеальное решение: быстрое, простое, надёжное.

---

## Подготовка окружения

В `docker-compose.yml` к PostgreSQL, MinIO и Adminer добавлен Redis:

```yaml
  redis:
    image: redis:7-alpine
    container_name: redis_session
    ports:
      - "6379:6379"
```

Запуск всего стека и приложения:

```bash
docker compose up -d          # postgres, minio, adminer, redis
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

Swagger: <http://127.0.0.1:8000/docs>

Настройки в `.env`:

```dotenv
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
SESSION_TTL=3600
```

---

## Что изменилось в проекте

| Файл | Изменение |
|---|---|
| `core/session.py` | **новый** — session store в Redis (create / get / destroy) |
| `api/deps.py` | **переписан** — константа `USER_ID=1` заменена на куку sessionId → Redis → пользователь из БД; `get_optional_user`, `require_user`, `ensure_owner` |
| `api/user.py` | register/login/logout вместо заглушек, установка HttpOnly-куки |
| `api/equipment.py` | guard'ы на методах создателя, `creator` из сессии, статусы 401/403/404/409, Swagger-описания |
| `api/schemas.py` | **новый** — Pydantic-модели ответов для Swagger |
| `main.py` | описание API, версия, `persistAuthorization` в Swagger UI |
| `docker-compose.yml`, `.env`, `core/config.py`, `requirements.txt` | Redis + `redis==8.1.0` |
| `postman/wifi-equipment.postman_collection.json` | коллекция лабы 4: auth + заголовок Cookie + гостевые 401 |

---

## Session store: работа с Redis

`core/session.py`:

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

Ключ — `session:<hex-uuid>`, значение — JSON с пользователем (в `redis-cli` сразу видно, кому принадлежит сессия), TTL — 1 час.

---

## Зависимости (guard'ы): текущий пользователь и права

`api/deps.py` — вместо синглтона-константы `get_current_user()` два варианта зависимости:

```python
COOKIE_NAME = "sessionId"

cookie_scheme = APIKeyCookie(
    name=COOKIE_NAME,
    description="Сессионная кука (HttpOnly), выдаваемая в Set-Cookie при POST /api/login ...",
    auto_error=False,
)


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Users | None:
    """Для открытых GET: без куки возвращает None (is_creator/is_liked = 0)."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        return None
    session = await get_session(session_id)
    if session is None:
        return None
    result = await db.execute(select(Users).where(Users.id_user == session["id_user"]))
    return result.scalar_one_or_none()


async def require_user(session_id: str | None = Depends(cookie_scheme), db: AsyncSession = Depends(get_db)) -> Users:
    """Для методов создателя: нет/истекла кука → 401."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Требуется аутентификация: нет куки sessionId")
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Сессия недействительна или истекла")
    ...
    return user


def ensure_owner(user: Users, equipment_creator: str) -> None:
    """Авторизация: операции с услугой — только её создателю, иначе 403."""
    if user.username != equipment_creator:
        raise HTTPException(status_code=403, detail="Недостаточно прав: услуга принадлежит другому пользователю")
```

`APIKeyCookie` из `fastapi.security` делает две вещи: помогает читать куку и добавляет в OpenAPI security-схему — в Swagger появляется кнопка **Authorize** у методов под замком.

---

## Домен пользователя: register / login / logout

`api/user.py` (форма — как в ТЗ, form-data):

```python
@router.post("/register", response_model=UserSchema, summary="Регистрация пользователя")
async def register(username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    existing = await db.execute(select(Users).where(Users.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")
    user = Users(username=username, password=password)
    db.add(user); await db.commit(); await db.refresh(user)
    return {"id_user": user.id_user, "username": user.username}


@router.post("/login", response_model=AuthResponseSchema, summary="Аутентификация (выдача сессии)")
async def login(response: Response, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    user = (await db.execute(select(Users).where(Users.username == username))).scalar_one_or_none()
    if user is None or user.password != password:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    session_id = await create_session(user.id_user, user.username)
    response.set_cookie(COOKIE_NAME, session_id, max_age=settings.SESSION_TTL,
                        httponly=True, samesite="lax", path="/")
    return {"user": {"id_user": user.id_user, "username": user.username}}


@router.post("/logout", summary="Деавторизация (уничтожение сессии)")
async def logout(response: Response, user=Depends(require_user), session_id=Depends(cookie_scheme)):
    await destroy_session(session_id)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
```

Правила доступа: `register`/`login` открыты (это и есть аутентификация), `logout` — метод с авторизацией (без куки → 401), как и остальные не-GET.

---

## Домен услуги: guard'ы, автозаполнение creator, статусы

`api/equipment.py`:

| Метод | URL | Доступ | Коды ответа |
|---|---|---|---|
| GET | `/api/equipments?freq_min=&freq_max=` | открытый | 200 (`is_creator` 0/1) |
| GET | `/api/equipment` | открытый | 200 (`like_count`, `is_liked` 0/1) |
| GET | `/api/equipment/{id}?next=true` | открытый | 200 / 404 |
| GET | `/api/equipment/draft` | создатель | 200 / **401** |
| POST | `/api/equipment` | создатель | 200 / **401** / 409 (уже есть черновик) |
| PUT | `/api/equipment/{id}` | создатель | 200 / **401** / **403** (чужая) / 404 / 409 (не черновик) |
| DELETE | `/api/equipment/{id}` | создатель | 200 / **401** / **403** / 404 |
| POST | `/api/equipment/{id}` (like) | создатель | 200 / **401** / 404 |

Автозаполнение пользователя при создании услуги и публикация:

```python
@router.post("/equipment", response_model=EquipmentSchema, summary="Создать черновик услуги (с картинкой и видео)")
async def create_equipment(
    title: str = Form(...),
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    user: Users = Depends(require_user),      # ← вместо константы USER_ID=1
    db: AsyncSession = Depends(get_db),
):
    ...
    equipment = Equipment(
        title=title,
        image_url=image_url,
        video_url=video_url,
        status=DRAFT,
        date_created=datetime.now(),
        creator=user.username,                # ← автор берётся из сессии
    )


@router.put("/equipment/{id_equipment}", response_model=EquipmentSchema, summary="Опубликовать услугу")
async def publish_equipment(id_equipment: int, description=Form(...), frequency=Form(...), ...,
                            user: Users = Depends(require_user), db=Depends(get_db)):
    equipment = ...
    if equipment is None:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    ensure_owner(user, equipment.creator)     # ← чужая услуга → 403
    if equipment.status != DRAFT:
        raise HTTPException(status_code=409, detail="Публикация возможна только из статуса «черновик»")
    ...
    equipment.status = PUBLISHED
    equipment.date_formed = datetime.now()
```

В открытых GET-методах признаки считаются для текущего пользователя (или для гостя):

```python
"is_creator": 1 if (user is not None and e.creator == user.username) else 0
"is_liked": 1 if is_liked else 0   # для гостя всегда 0
```

---

## Swagger: описание методов и Authorize

`main.py`:

```python
app = FastAPI(
    title="Wi-Fi Equipment API",
    description=DESCRIPTION,          # правила доступа + как получить куку
    version="4.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)
```

У каждого эндпоинта — `summary`, `description`, `responses` (401/403/404/409), у полей — `description`; модели ответов (`api/schemas.py`) описывают поля в Swagger. Методы под `Depends(require_user)` автоматически получают security-схему `sessionId` — у них в Swagger значок замка и кнопка **Authorize**.

Как тестировать в Swagger:

1. Откройте <http://127.0.0.1:8000/docs> **в режиме инкогнито** (чистые куки).
2. `POST /api/register` → 200 с `{id_user, username}`.
3. `POST /api/login` → в ответе `Set-Cookie: sessionId=...; HttpOnly` — браузер запомнит куку, и все дальнейшие запросы из этой вкладки уже авторизованы.
4. Анонимные GET (`/api/equipments`, `/api/equipment`) работают и без куки.
5. Методы под замком без куки вернут 401; с кукой — 200.
6. Альтернатива: нажмите **Authorize** и вставьте значение `sessionId` из вкладки Application → Cookies (Postman/Insomnia: заголовок `Cookie: sessionId=значение`).

---

## Тестирование

### 1. Swagger (инкогнито)

- Регистрация → 200, логин → 200 + `Set-Cookie` (скриншоты 1–3).
- GET списка услуг в Swagger после логина (кука браузера подставляется сама).

### 2. Postman / Insomnia

Коллекция `postman/wifi-equipment.postman_collection.json` (проверена в newman: 15 запросов, 43/43 проверки):

- `{{base_url}}` = `http://127.0.0.1:8000` — авторизованные запросы с заголовком `Cookie: sessionId={{session_id}}`;
- `{{anon_url}}` = `http://localhost:8000` — анонимные/гостевые запросы (куки-джар Postman на них не распространяется, поэтому 401 честный);
- после `POST /api/login` значение куки из `Set-Cookie` сохраняется в `{{session_id}}`; `id` созданной услуги — в `{{equipment_id}}`.

Прогон по порядку: регистрация → логин → список (без куки, 200) → черновик/создание без куки (401) → создание с кукой (200, `creator` = username) → поля черновика → публикация без куки (401) → публикация с кукой (200, статус «опубликован») → лента без ид и по ид `?next=true` (без куки) → лайк → удаление → logout → повторный запрос с той же кукой (401).

Чужая услуга: второй пользователь пытается опубликовать/удалить чужой черновик → 403 (в смоук-тесте проекта).

### 3. Redis через cmd

После логина в Swagger/Postman посмотрите содержимое Redis:

```bat
docker exec redis_session redis-cli KEYS "session:*"
docker exec redis_session redis-cli GET "session:6099e7c01da54dcebd367d64455dfe2c"
docker exec redis_session redis-cli TTL "session:6099e7c01da54dcebd367d64455dfe2c"
```

```text
1) "session:6099e7c01da54dcebd367d64455dfe2c"
{"id_user": 13, "username": "stuba33a4a5"}
(integer) 3016
```

В ключе сессии виден пользователь. После `POST /api/logout` ключ исчезает (`GET` → `(nil)`) — деавторизация мгновенная.

---

## Порядок показа и скриншоты

| № | Что снимать |
|---|---|
| 1 | Swagger (инкогнито): `POST /api/register` → 200 |
| 2 | Swagger: `POST /api/login` → 200, в ответе `Set-Cookie: sessionId=...; HttpOnly` |
| 3 | Swagger: список услуг после логина (GET `/api/equipments` → 200) |
| 4 | Postman: GET списка без токена/куки → 200 (работает независимо) |
| 5 | Postman: GET ленты без токена/куки → 200 |
| 6 | Postman/Insomnia: PUT публикации **без куки** → 401 (для чужой услуги — 403) |
| 7 | Postman: PUT публикации **с кукой** (`Cookie: sessionId=...`) → 200, поля обновлены, статус «опубликован» |
| 8 | cmd: `redis-cli KEYS "session:*"` и `GET session:<id>` — в ключе сессии пользователь; после logout ключ удалён |
| 9 | StarUML: sequence-диаграмма, у сообщений в properties заполнено поле `signature` (переиспользовано из диаграммы классов) |

Sequence-диаграмма (StarUML) — весь набор HTTP-запросов бизнес-процесса без БД и нативного приложения: аутентификация → GET списка с фильтром → добавление услуги с картинкой и видео → поля черновика → публикация → лента без ид → лента по ид `?next=true` → лайк. В качестве Lifeline — домены, в `arguments` сообщений — ключевые входные/выходные данные (username/password; sessionId; title/image/video; id_equipment и т.д.).

---

## Контрольные вопросы

**Куки** — небольшие пары «имя=значение», которые сервер отправляет в заголовке `Set-Cookie`, а клиент возвращает в каждом запросе в заголовке `Cookie`. Флаг `HttpOnly` запрещает доступ к куке из JS (защита от XSS), `SameSite=Lax` снижает риск CSRF, `Max-Age` задаёт время жизни. У нас HttpOnly-кука `sessionId` — идентификатор сессии.

**Сессия** — состояние «пользователь залогинен» на стороне сервера. Идентификатор сессии живёт в куке, а сами данные сессии (id пользователя) — в Redis. Stateful-подход в отличие от stateless JWT: logout и истечение TTL работают мгновенно.

**Redis** — быстрый key-value store «в памяти» с TTL. Для сессий он хранит пары `session:<id> → userId/JSON`, переживает перезапуски приложения, позволяет смотреть активные сессии из `redis-cli` и одинаково хорошо работает за несколькими инстансами сервиса.

**JWT** — самодостаточный подписанный токен (header.payload.signature, подписанный секретом или RSA-ключом). Не требует серверного хранения, поэтому для него делают «чёрный список» отозванных токенов (в т.ч. в Redis). В этой лабораторной для FastAPI выбран сессионный подход с кукой; JWT+blacklist — вариант для Golang-части.

**Аутентификация vs авторизация** — «кто ты?» (проверка логина/пароля → выдача сессии) против «что тебе можно?» (401 без сессии, 403 для чужой услуги). В коде: `require_user` (аутентификация) и `ensure_owner` (авторизация).

**SSO (Single Sign On)** — единый вход: после одной аутентификации пользователь получает доступ ко множеству сервисов (Kerberos, SAML, OAuth2/OIDC, общие сессии на домене). Наш сервис — один домен, но принцип тот же: одна сессия = один вход.

**Двухфакторная аутентификация (2FA)** — второй фактор помимо пароля: код из SMS/приложения (TOTP), hardware-ключ. Даже украденный пароль не даёт входа без второго фактора. Может комбинироваться с JWT/сессиями.

**RSA** — асимметричный алгоритм: есть пара ключей (public/private). Используется в цифровых подписях (JWT подписывается приватным ключом, проверяется публичным), в TLS/SSH и для шифрования (публичный ключ шифрует, приватный расшифровывает).

---

## Заключение

Реализовано:

- ✅ сессионная аутентификация через HttpOnly-куку `sessionId`;
- ✅ сессии в Redis с TTL и JSON-значением (виден пользователь);
- ✅ register / login / logout с Swagger-описаниями;
- ✅ модель доступа «без авторизации — только чтение, с авторизацией — методы создателя» (401/403/404/409);
- ✅ автозаполнение `creator` из сессии при создании услуги;
- ✅ Swagger с Authorize и описаниями всех методов;
- ✅ Postman-коллекция с заголовком Cookie, гостевыми 401 и проверками (прогнана в newman).

### Полезные ссылки

- [FastAPI — Authentication](https://fastapi.tiangolo.com/tutorial/security/)
- [FastAPI — Using the Request directly / dependencies](https://fastapi.tiangolo.com/dependencies/dependencies-with-parameters/)
- [redis-py (asyncio)](https://redis.readthedocs.io/en/stable/asyncio_client.html)
- [OWASP: Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP: Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
