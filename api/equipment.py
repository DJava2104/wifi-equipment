from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import ensure_owner, get_optional_user, require_user
from api.schemas import EquipmentListItemSchema, EquipmentSchema, FeedItemSchema, LikeResponseSchema
from api.serializers import equipment_serializer
from db.session import get_db
from minio_client import upload_file
from models.equipment import Equipment
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


async def _feed_out(db: AsyncSession, equipment: Equipment, user: Users | None) -> dict:
    like_count = (
        await db.execute(
            select(func.count())
            .select_from(Likes)
            .where(Likes.id_equipment == equipment.id_equipment)
        )
    ).scalar_one()
    is_liked = False
    if user is not None:
        is_liked = (
            await db.execute(
                select(Likes)
                .where(Likes.id_equipment == equipment.id_equipment)
                .where(Likes.id_user == user.id_user)
            )
        ).scalar_one_or_none() is not None
    out = equipment_serializer(equipment)
    out["like_count"] = like_count
    out["is_liked"] = 1 if is_liked else 0
    return out


@router.get(
    "/equipments",
    response_model=list[EquipmentListItemSchema],
    summary="Список опубликованных услуг с фильтром по частоте",
    description=(
        "Открытый метод (без авторизации). `freq_min`/`freq_max` — диапазон частоты, ГГц. "
        "Поле `is_creator` = 1, если создатель совпадает с текущим пользователем "
        "(для гостя всегда 0)."
    ),
)
async def get_equipments(
    freq_min: float | None = Query(None, description="Минимальная частота, ГГц"),
    freq_max: float | None = Query(None, description="Максимальная частота, ГГц"),
    user: Users | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Equipment).where(Equipment.status == PUBLISHED)
    if freq_min is not None:
        stmt = stmt.where(Equipment.frequency >= freq_min)
    if freq_max is not None:
        stmt = stmt.where(Equipment.frequency <= freq_max)
    result = await db.execute(stmt)
    equipments = result.scalars().all()
    return [
        {
            **equipment_serializer(e),
            "is_creator": 1 if (user is not None and e.creator == user.username) else 0,
        }
        for e in equipments
    ]


@router.get(
    "/equipment/draft",
    response_model=EquipmentSchema | None,
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
        select(Equipment)
        .where(Equipment.status == DRAFT)
        .where(Equipment.creator == user.username)
        .limit(1)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        return None
    return equipment_serializer(equipment)


@router.get(
    "/equipment",
    response_model=FeedItemSchema,
    summary="Лента: текущая опубликованная услуга",
    description=(
        "Открытый метод (без авторизации). Возвращает первое опубликованное "
        "устройство (или по `id_equipment`, если указан) + `like_count` и `is_liked`. "
        "`next=true` — следующее после указанного с переходом по кругу."
    ),
)
@router.get(
    "/equipment/{id_equipment}",
    response_model=FeedItemSchema,
    summary="Лента: опубликованная услуга по ид",
    description=(
        "Открытый метод (без авторизации). `next=true` — вернуть следующее "
        "опубликованное после указанного (цикл). `is_liked` для гостя всегда 0."
    ),
    responses={404: {"description": "Нет опубликованных услуг или ид не найден"}},
)
async def get_equipment(
    id_equipment: int | None = None,
    go_next: bool = Query(False, alias="next", description="Следующее после указанного (по кругу)"),
    user: Users | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Equipment)
        .where(Equipment.status == PUBLISHED)
        .order_by(Equipment.id_equipment)
    )
    published = result.scalars().all()
    if not published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нет опубликованных услуг")

    if id_equipment is None:
        idx = 0
    else:
        idx = next(
            (i for i, e in enumerate(published) if e.id_equipment == id_equipment),
            None,
        )
        if idx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")

    if go_next:
        idx = (idx + 1) % len(published)

    return await _feed_out(db, published[idx], user)


@router.post(
    "/equipment",
    response_model=EquipmentSchema,
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
async def create_equipment(
    title: str = Form(..., description="Название услуги"),
    image: UploadFile = File(..., description="Изображение (jpg/png)"),
    video: UploadFile = File(..., description="Видео (mp4)"),
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Equipment)
        .where(Equipment.status == DRAFT)
        .where(Equipment.creator == user.username)
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У пользователя уже есть черновик",
        )

    image_url = upload_file(await image.read(), image.filename)
    video_url = upload_file(await video.read(), video.filename)

    equipment = Equipment(
        title=title,
        image_url=image_url,
        video_url=video_url,
        status=DRAFT,
        date_created=datetime.now(),
        creator=user.username,
    )
    db.add(equipment)
    await db.commit()
    await db.refresh(equipment)
    return equipment_serializer(equipment)


@router.put(
    "/equipment/{id_equipment}",
    response_model=EquipmentSchema,
    summary="Опубликовать услугу (черновик → опубликован)",
    description=(
        "Метод создателя. Заполняет описательные поля, вычисляет `band`, "
        "переводит статус в «опубликован» и фиксирует `date_formed`. "
        "Гость получает 401, чужую услугу опубликовать нельзя — 403."
    ),
    responses={**OWNER_ONLY, 409: {"description": "Услуга не в статусе «черновик»"}},
)
async def publish_equipment(
    id_equipment: int,
    description: str = Form(..., description="Описание услуги"),
    frequency: float = Form(..., description="Частота, ГГц (из неё вычисляется band)"),
    standard: str = Form("", description="Стандарт Wi-Fi (802.11ac и т.п.)"),
    max_speed: int | None = Form(None, description="Макс. скорость, Мбит/с"),
    antennas: str | None = Form("", description="Количество антенн"),
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Equipment).where(Equipment.id_equipment == id_equipment)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    ensure_owner(user, equipment.creator)
    if equipment.status != DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Публикация возможна только из статуса «{DRAFT}»",
        )

    equipment.description = description
    equipment.frequency = frequency
    equipment.band = f"{frequency} ГГц"
    equipment.standard = standard or None
    equipment.max_speed = max_speed
    equipment.antennas = antennas or None
    equipment.status = PUBLISHED
    equipment.date_formed = datetime.now()
    await db.commit()
    await db.refresh(equipment)
    return equipment_serializer(equipment)


@router.delete(
    "/equipment/{id_equipment}",
    status_code=200,
    summary="Мягкое удаление услуги (только свои)",
    description="Метод создателя. Статус меняется на «удалён», тело ответа пустое.",
    responses=OWNER_ONLY,
)
async def delete_equipment(
    id_equipment: int,
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Equipment).where(Equipment.id_equipment == id_equipment)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    ensure_owner(user, equipment.creator)
    if equipment.status == DELETED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга уже удалена")

    equipment.status = DELETED
    equipment.date_completed = datetime.now()
    await db.commit()
    return Response(status_code=200)


@router.post(
    "/equipment/{id_equipment}",
    response_model=LikeResponseSchema,
    summary="Поставить/снять лайк",
    description="Метод создателя. Form-поле `like`: 1 — поставить, 0 — отменить. Ответ: {like_count}.",
    responses=OWNER_ONLY,
)
async def like_equipment(
    id_equipment: int,
    like: int = Form(..., description="1 — поставить лайк, 0 — отменить"),
    user: Users = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Equipment).where(Equipment.id_equipment == id_equipment)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")

    existing = await db.execute(
        select(Likes)
        .where(Likes.id_user == user.id_user)
        .where(Likes.id_equipment == id_equipment)
    )
    like_row = existing.scalar_one_or_none()

    if like == 1 and like_row is None:
        db.add(Likes(id_user=user.id_user, id_equipment=id_equipment))
        await db.commit()
    elif like == 0 and like_row is not None:
        await db.delete(like_row)
        await db.commit()

    count = (
        await db.execute(
            select(func.count())
            .select_from(Likes)
            .where(Likes.id_equipment == id_equipment)
        )
    ).scalar_one()
    return {"like_count": count}
