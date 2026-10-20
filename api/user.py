from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import COOKIE_NAME, cookie_scheme, require_user
from api.schemas import AuthResponseSchema, UserSchema
from core.config import settings
from core.session import create_session, destroy_session
from db.session import get_db
from models.users import Users

router = APIRouter(prefix="/api", tags=["Пользователь"])


@router.post(
    "/register",
    response_model=UserSchema,
    summary="Регистрация пользователя",
    description=(
        "Создаёт запись в таблице `users`. Логин должен быть уникален — "
        "иначе возвращается 409. Авторизация после регистрации не выдаётся: "
        "выполните POST /api/login."
    ),
    responses={409: {"description": "Логин уже занят"}},
)
async def register(
    username: str = Form(..., description="Логин (уникальный)"),
    password: str = Form(..., description="Пароль (хранится открытым текстом, как в таблице users)"),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Users).where(Users.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует",
        )

    user = Users(username=username, password=password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id_user": user.id_user, "username": user.username}


@router.post(
    "/login",
    response_model=AuthResponseSchema,
    summary="Аутентификация (выдача сессии)",
    description=(
        "Проверяет логин и пароль, создаёт сессию в Redis "
        "(`session:<id>` → JSON с id_user и username) и устанавливает "
        "HttpOnly-куку sessionId. Значение куки используется во всех "
        "авторизованных запросах (Swagger / Postman / Insomnia)."
    ),
    responses={
        401: {"description": "Неверный логин или пароль"},
        200: {
            "description": "Успешная аутентификация, в заголовке Set-Cookie — sessionId",
            "headers": {
                "Set-Cookie": {
                    "description": "sessionId=<hex>; HttpOnly; Path=/; Max-Age=3600",
                    "schema": {"type": "string"},
                }
            },
        },
    },
)
async def login(
    response: Response,
    username: str = Form(..., description="Логин"),
    password: str = Form(..., description="Пароль"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Users).where(Users.username == username))
    user = result.scalar_one_or_none()
    if user is None or user.password != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

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


@router.post(
    "/logout",
    summary="Деавторизация (уничтожение сессии)",
    description=(
        "Метод с авторизацией: удаляет сессию из Redis и очищает куку sessionId — "
        "мгновенная деавторизация. Без валидной куки — 401 (без авторизации доступно "
        "только чтение)."
    ),
    responses={401: {"description": "Нет валидной сессии (кука sessionId)"}},
)
async def logout(
    response: Response,
    user: Users = Depends(require_user),
    session_id: str | None = Depends(cookie_scheme),
):
    await destroy_session(session_id)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}
