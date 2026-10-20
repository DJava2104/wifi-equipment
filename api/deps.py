from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.session import get_session
from db.session import get_db
from models.users import Users

COOKIE_NAME = "sessionId"

cookie_scheme = APIKeyCookie(
    name=COOKIE_NAME,
    description=(
        "Сессионная кука (HttpOnly), выдаваемая в Set-Cookie при POST /api/login. "
        "В Swagger: выполните login в этом же окне браузера — кука подставится сама, "
        "либо нажмите Authorize и вставьте значение куки из вкладки Application → Cookies. "
        "В Postman/Insomnia передавайте заголовок Cookie: sessionId=значение."
    ),
    auto_error=False,
)


async def _load_user(db: AsyncSession, user_id: int) -> Users | None:
    result = await db.execute(select(Users).where(Users.id_user == user_id))
    return result.scalar_one_or_none()


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Users | None:
    """Текущий пользователь из куки sessionId, если сессия валидна; иначе None.

    Используется в открытых (чтение) методах: без авторизации запрос тоже работает,
    но признаки is_creator/is_liked считаются для гостя (0).
    """
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
    """Текущий пользователь из сессии в Redis; без валидной куки — 401."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация: нет куки sessionId",
        )
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия недействительна или истекла",
        )
    user = await _load_user(db, session["id_user"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь сессии не найден",
        )
    return user


def ensure_owner(user: Users, equipment_creator: str) -> None:
    """Авторизация: выполнять операции с услугой может только её создатель."""
    if user.username != equipment_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав: услуга принадлежит другому пользователю",
        )
