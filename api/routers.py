from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.serializers import router_serializer
from db.session import get_db
from minio_client import upload_file
from models.routers import Router
from models.likes import Likes

router = APIRouter(prefix="/api")

DRAFT = "черновик"
PUBLISHED = "опубликован"
DELETED = "удален"


async def _feed_out(db: AsyncSession, router: Router) -> dict:
    current_user = get_current_user()
    like_count = (
        await db.execute(
            select(func.count())
            .select_from(Likes)
            .where(Likes.id_routers == router.id_routers)
        )
    ).scalar_one()
    is_liked = (
        await db.execute(
            select(Likes)
            .where(Likes.id_routers == router.id_routers)
            .where(Likes.id_user == current_user.USER_ID)
        )
    ).scalar_one_or_none() is not None
    out = router_serializer(router)
    out["like_count"] = like_count
    out["is_liked"] = 1 if is_liked else 0
    return out


@router.get("/routers")
async def get_routers(
    freq_min: float | None = Query(None),
    freq_max: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    stmt = select(Router).where(Router.status == PUBLISHED)
    if freq_min is not None:
        stmt = stmt.where(Router.frequency >= freq_min)
    if freq_max is not None:
        stmt = stmt.where(Router.frequency <= freq_max)
    result = await db.execute(stmt)
    routers = result.scalars().all()
    return [
        {
            **router_serializer(e),
            "is_creator": 1 if e.creator == current_user.USERNAME else 0,
        }
        for e in routers
    ]


@router.get("/router/draft")
async def get_draft(db: AsyncSession = Depends(get_db)):
    current_user = get_current_user()
    result = await db.execute(
        select(Router)
        .where(Router.status == DRAFT)
        .where(Router.creator == current_user.USERNAME)
        .limit(1)
    )
    router = result.scalar_one_or_none()
    if router is None:
        return None
    return router_serializer(router)


@router.get("/router")
@router.get("/router/{id_routers}")
async def get_router(
    id_routers: int | None = None,
    go_next: bool = Query(False, alias="next"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Router)
        .where(Router.status == PUBLISHED)
        .order_by(Router.id_routers)
    )
    published = result.scalars().all()
    if not published:
        return Response(status_code=404)

    if id_routers is None:
        idx = 0
    else:
        idx = next(
            (i for i, e in enumerate(published) if e.id_routers == id_routers),
            None,
        )
        if idx is None:
            return Response(status_code=404)

    if go_next:
        idx = (idx + 1) % len(published)

    return await _feed_out(db, published[idx])


@router.post("/router")
async def create_router(
    title: str = Form(...),
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    frequency: float | None = Form(None),
    max_speed: int | None = Form(None),
    standard: str = Form(""),
    antennas: str = Form(""),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    existing = await db.execute(
        select(Router)
        .where(Router.status == DRAFT)
        .where(Router.creator == current_user.USERNAME)
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return Response(status_code=500)

    image_url = upload_file(await image.read(), image.filename)
    video_url = upload_file(await video.read(), video.filename)

    router = Router(
        title=title,
        image_url=image_url,
        video_url=video_url,
        frequency=frequency,
        max_speed=max_speed,
        standard=standard or None,
        antennas=antennas or None,
        description=description or None,
        band=f"{frequency} ГГц" if frequency is not None else None,
        status=DRAFT,
        date_created=datetime.now(),
        creator=current_user.USERNAME,
    )
    db.add(router)
    await db.commit()
    await db.refresh(router)
    return router_serializer(router)


@router.put("/router/{id_routers}")
async def publish_router(
    id_routers: int,
    description: str = Form(...),
    frequency: float = Form(...),
    standard: str = Form(""),
    max_speed: int | None = Form(None),
    antennas: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    result = await db.execute(
        select(Router).where(Router.id_routers == id_routers)
    )
    router = result.scalar_one_or_none()
    if router is None:
        return Response(status_code=404)
    if router.status != DRAFT:
        return Response(status_code=500)
    if router.creator != current_user.USERNAME:
        return Response(status_code=500)

    router.description = description
    router.frequency = frequency
    router.band = f"{frequency} ГГц"
    router.standard = standard or None
    router.max_speed = max_speed
    router.antennas = antennas or None
    router.status = PUBLISHED
    router.date_formed = datetime.now()
    await db.commit()
    await db.refresh(router)
    return router_serializer(router)


@router.delete("/router/{id_routers}")
async def delete_router(
    id_routers: int,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    result = await db.execute(
        select(Router).where(Router.id_routers == id_routers)
    )
    router = result.scalar_one_or_none()
    if router is None:
        return Response(status_code=404)
    if router.creator != current_user.USERNAME:
        return Response(status_code=500)
    if router.status == DELETED:
        return Response(status_code=404)

    router.status = DELETED
    router.date_completed = datetime.now()
    await db.commit()
    return Response(status_code=200)


@router.post("/router/{id_routers}")
async def like_router(
    id_routers: int,
    like: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user()
    existing = await db.execute(
        select(Likes)
        .where(Likes.id_user == current_user.USER_ID)
        .where(Likes.id_routers == id_routers)
    )
    like_row = existing.scalar_one_or_none()

    if like == 1 and like_row is None:
        db.add(Likes(id_user=current_user.USER_ID, id_routers=id_routers))
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
