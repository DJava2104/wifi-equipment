from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.serializers import equipment_serializer
from db.session import get_db
from minio_client import upload_file
from models.equipment import Equipment
from models.likes import Likes

router = APIRouter(prefix="/api")

DRAFT = "черновик"
PUBLISHED = "опубликован"
DELETED = "удален"


async def _feed_out(db: AsyncSession, equipment: Equipment) -> dict:
    current_user = get_current_user()
    like_count = (
        await db.execute(
            select(func.count())
            .select_from(Likes)
            .where(Likes.id_equipment == equipment.id_equipment)
        )
    ).scalar_one()
    is_liked = (
        await db.execute(
            select(Likes)
            .where(Likes.id_equipment == equipment.id_equipment)
            .where(Likes.id_user == current_user.USER_ID)
        )
    ).scalar_one_or_none() is not None
    out = equipment_serializer(equipment)
    out["like_count"] = like_count
    out["is_liked"] = 1 if is_liked else 0
    return out


@router.get("/equipments")
async def get_equipments(
    freq_min: float | None = Query(None),
    freq_max: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
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
            "is_creator": 1 if e.creator == current_user.USERNAME else 0,
        }
        for e in equipments
    ]


@router.get("/equipment/draft")
async def get_draft(db: AsyncSession = Depends(get_db)):
    current_user = get_current_user()
    result = await db.execute(
        select(Equipment)
        .where(Equipment.status == DRAFT)
        .where(Equipment.creator == current_user.USERNAME)
        .limit(1)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        return None
    return equipment_serializer(equipment)


@router.get("/equipment")
@router.get("/equipment/{id_equipment}")
async def get_equipment(
    id_equipment: int | None = None,
    go_next: bool = Query(False, alias="next"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Equipment)
        .where(Equipment.status == PUBLISHED)
        .order_by(Equipment.id_equipment)
    )
    published = result.scalars().all()
    if not published:
        return Response(status_code=404)

    if id_equipment is None:
        idx = 0
    else:
        idx = next(
            (i for i, e in enumerate(published) if e.id_equipment == id_equipment),
            None,
        )
        if idx is None:
            return Response(status_code=404)

    if go_next:
        idx = (idx + 1) % len(published)

    return await _feed_out(db, published[idx])


@router.post("/equipment")
async def create_equipment(
    title: str = Form(...),
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    existing = await db.execute(
        select(Equipment)
        .where(Equipment.status == DRAFT)
        .where(Equipment.creator == current_user.USERNAME)
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return Response(status_code=500)

    image_url = upload_file(await image.read(), image.filename)
    video_url = upload_file(await video.read(), video.filename)

    equipment = Equipment(
        title=title,
        image_url=image_url,
        video_url=video_url,
        status=DRAFT,
        date_created=datetime.now(),
        creator=current_user.USERNAME,
    )
    db.add(equipment)
    await db.commit()
    await db.refresh(equipment)
    return equipment_serializer(equipment)


@router.put("/equipment/{id_equipment}")
async def publish_equipment(
    id_equipment: int,
    description: str = Form(...),
    frequency: float = Form(...),
    standard: str = Form(""),
    max_speed: int | None = Form(None),
    antennas: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    result = await db.execute(
        select(Equipment).where(Equipment.id_equipment == id_equipment)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        return Response(status_code=404)
    if equipment.status != DRAFT:
        return Response(status_code=500)
    if equipment.creator != current_user.USERNAME:
        return Response(status_code=500)

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


@router.delete("/equipment/{id_equipment}")
async def delete_equipment(
    id_equipment: int,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    result = await db.execute(
        select(Equipment).where(Equipment.id_equipment == id_equipment)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        return Response(status_code=404)
    if equipment.creator != current_user.USERNAME:
        return Response(status_code=500)
    if equipment.status == DELETED:
        return Response(status_code=404)

    equipment.status = DELETED
    equipment.date_completed = datetime.now()
    await db.commit()
    return Response(status_code=200)


@router.post("/equipment/{id_equipment}")
async def like_equipment(
    id_equipment: int,
    like: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    existing = await db.execute(
        select(Likes)
        .where(Likes.id_user == current_user.USER_ID)
        .where(Likes.id_equipment == id_equipment)
    )
    like_row = existing.scalar_one_or_none()

    if like == 1 and like_row is None:
        db.add(Likes(id_user=current_user.USER_ID, id_equipment=id_equipment))
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
