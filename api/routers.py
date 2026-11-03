from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import ensure_owner, get_optional_user, require_user
from api.schemas import FeedItemSchema, LikeResponseSchema, RouterListItemSchema, RouterSchema
from api.serializers import router_serializer
from db.session import get_db
from minio_client import upload_file
from models.routers import Router
from models.likes import Likes
from models.users import Users

router = APIRouter(prefix="/api", tags=["Услуга"])

DRAFT = "черновик"
PUBLISHED = "опубликован"
DELETED = "удален"

AUTH_REQUIRED = {401: {"description": "Нет валидной сессии (кука sessionId)"}}
OWNER_ONLY = {
    **AUTH_REQUIRED,
    403: {"description": "Нет прав: услуга принадлежит другому пользователю"},
    404: {"description": "Услуга не найдена"},
}


async def _feed_out(db: AsyncSession, item: Router, user: Users | None) -> dict:
    like_count = (
        await db.execute(
            select(func.count())
            .select_from(Likes)
            .where(Likes.id_routers == item.id_routers)
        )
    ).scalar_one()
    is_liked = False
    if user is not None:
        is_liked = (
            await db.execute(
                select(Likes)
                .where(Likes.id_routers == item.id_routers)
                .where(Likes.id_user == user.id_user)
            )
        ).scalar_one_or_none() is not None
    out = router_serializer(item)
    out["like_count"] = like_count
    out["is_liked"] = 1 if is_liked else 0
    return out


@router.get(
    "/routers",
    response_model=list[RouterListItemSchema],
    summary="Список опубликованных услуг с фильтром по частоте",
    description=(
        "Открытый метод (без авторизации). `freq_min`/`freq_max` — диапазон частоты, ГГц. "
        "Поле `is_creator` = 1, если создатель совпадает с текущим пользователем "
        "(для гостя всегда 0)."
    ),
)
async def get_routers(
    freq_min: float | None = Query(None, description="Минимальная частота, ГГц"),
    freq_max: float | None = Query(None, description="Максимальная частота, ГГц"),
    user: Users | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Router).where(Router.status == PUBLISHED)
    if freq_min is not None:
        stmt = stmt.where(Router.frequency >= freq_min)
    if freq_max is not None:
        stmt = stmt.where(Router.frequency <= freq_max)
    result = await db.execute(stmt)
    routers_list = result.scalars().all()
    return [
        {
            **router_serializer(e),
            "is_creator": 1 if (user is not None and e.creator == user.username) else 0,
        }
        for e in routers_list
    ]


@router.get(
    "/router/draft",
    response_model=RouterSchema | None,
    summary="Черновик текущего пользователя",
    description=(
        "Метод создателя: возвращает не более одной черновики текущего пользователя "
        "или null. Требуется кука sessionId."
    ),
    responses=AUTH_REQUIRED,
)
async def get_draft(
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Router)
        .where(Router.status == DRAFT)
        .where(Router.creator == user.username)
        .limit(1)
    )
    item = result.scalar_one_or_none()
    if item is None:
        return None
    return router_serializer(item)


@router.get(
    "/router",
    response_model=FeedItemSchema,
    summary="Лента: текущая опубликованная услуга",
    description=(
        "Открытый метод (без авторизации). Возвращает первое опубликованное "
        "устройство (или по `id_routers`, если указан) + `like_count` и `is_liked`. "
        "`next=true` — следующее после указанного с переходом по кругу."
    ),
)
@router.get(
    "/router/{id_routers}",
    response_model=FeedItemSchema,
    summary="Лента: опубликованная услуга по ид",
    description=(
        "Открытый метод (без авторизации). `next=true` — вернуть следующее "
        "опубликованное после указанного (цикл). `is_liked` для гостя всегда 0."
    ),
    responses={404: {"description": "Нет опубликованных услуг или ид не найден"}},
)
async def get_router(
    id_routers: int | None = None,
    go_next: bool = Query(False, alias="next", description="Следующее после указанного (по кругу)"),
    user: Users | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Router)
        .where(Router.status == PUBLISHED)
        .order_by(Router.id_routers)
    )
    published = result.scalars().all()
    if not published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нет опубликованных услуг")

    if id_routers is None:
        idx = 0
    else:
        idx = next(
            (i for i, e in enumerate(published) if e.id_routers == id_routers),
            None,
        )
        if idx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")

    if go_next:
        idx = (idx + 1) % len(published)

    return await _feed_out(db, published[idx], user)


@router.post(
    "/router",
    response_model=RouterSchema,
    status_code=200,
    summary="Создать черновик услуги (с картинкой и видео)",
    description=(
        "Метод создателя. Файлы `image` и `video` загружаются в MinIO, "
        "в БД записываются их латинские имена (uuid.ext). "
        "`creator` заполняется автоматически из сессии. "
        "Не более одного черновика на пользователя."
    ),
    responses={
        **OWNER_ONLY,
        409: {"description": "У пользователя уже есть черновик"},
    },
)
async def create_router(
    title: str = Form(..., description="Название услуги"),
    image: UploadFile = File(..., description="Изображение (jpg/png)"),
    video: UploadFile = File(..., description="Видео (mp4)"),
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Router)
        .where(Router.status == DRAFT)
        .where(Router.creator == user.username)
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У пользователя уже есть черновик",
        )

    image_url = upload_file(await image.read(), image.filename)
    video_url = upload_file(await video.read(), video.filename)

    item = Router(
        title=title,
        image_url=image_url,
        video_url=video_url,
        status=DRAFT,
        date_created=datetime.now(),
        creator=user.username,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return router_serializer(item)


@router.put(
    "/router/{id_routers}",
    response_model=RouterSchema,
    summary="Опубликовать услугу (черновик → опубликован)",
    description=(
        "Метод создателя. Заполняет описательные поля, вычисляет `band`, "
        "переводит статус в «опубликован» и фиксирует `date_formed`. "
        "Гость получает 401, чужую услугу опубликовать нельзя — 403."
    ),
    responses={**OWNER_ONLY, 409: {"description": "Услуга не в статусе «черновик»"}},
)
async def publish_router(
    id_routers: int,
    description: str = Form(..., description="Описание услуги"),
    frequency: float = Form(..., description="Частота, ГГц (из неё вычисляется band)"),
    standard: str = Form("", description="Стандарт Wi-Fi (802.11ac и т.п.)"),
    max_speed: int | None = Form(None, description="Макс. скорость, Мбит/с"),
    antennas: str | None = Form("", description="Количество антенн"),
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Router).where(Router.id_routers == id_routers)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    ensure_owner(user, item.creator)
    if item.status != DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Публикация возможна только из статуса «{DRAFT}»",
        )

    item.description = description
    item.frequency = frequency
    item.band = f"{frequency} ГГц"
    item.standard = standard or None
    item.max_speed = max_speed
    item.antennas = antennas or None
    item.status = PUBLISHED
    item.date_formed = datetime.now()
    await db.commit()
    await db.refresh(item)
    return router_serializer(item)


@router.delete(
    "/router/{id_routers}",
    status_code=200,
    summary="Мягкое удаление услуги (только свои)",
    description="Метод создателя. Статус меняется на «удалён», тело ответа пустое.",
    responses=OWNER_ONLY,
)
async def delete_router(
    id_routers: int,
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Router).where(Router.id_routers == id_routers)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    ensure_owner(user, item.creator)
    if item.status == DELETED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга уже удалена")

    item.status = DELETED
    item.date_completed = datetime.now()
    await db.commit()
    return Response(status_code=200)


@router.post(
    "/router/{id_routers}",
    response_model=LikeResponseSchema,
    summary="Поставить/снять лайк",
    description="Метод создателя. Form-поле `like`: 1 — поставить, 0 — отменить. Ответ: {like_count}.",
    responses=OWNER_ONLY,
)
async def like_router(
    id_routers: int,
    like: int = Form(..., ge=0, le=1, description="1 — поставить лайк, 0 — отменить"),
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Router)
        .where(Router.id_routers == id_routers)
        .where(Router.status == PUBLISHED)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Опубликованная услуга не найдена",
        )

    existing = await db.execute(
        select(Likes)
        .where(Likes.id_user == user.id_user)
        .where(Likes.id_routers == id_routers)
    )
    like_row = existing.scalar_one_or_none()

    if like == 1 and like_row is None:
        db.add(Likes(id_user=user.id_user, id_routers=id_routers))
        await db.commit()
    elif like == 0 and like_row is not None:
        await db.delete(like_row)
        await db.commit()

    count = (
        await db.execute(
            select(func.count())
            .select_from(Likes)
            .where(Likes.id_routers == id_routers)
        )
    ).scalar_one()
    return {"like_count": count}
