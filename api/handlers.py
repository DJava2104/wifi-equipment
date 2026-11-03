from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.routers import Router
from models.likes import Likes

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CURRENT_USER = "user_0"

FREQ_MIN = 2.4
FREQ_MAX = 6.0

PUBLISHED = "опубликован"


def ghz(value) -> str:
    """5.0 -> '5 ГГц', 2.4 -> '2.4 ГГц'."""
    if value is None:
        return "—"
    return f"{value:g} ГГц"


templates.env.filters["ghz"] = ghz


async def get_draft(user: str, db: AsyncSession):
    stmt = (
        select(Router)
        .where(Router.creator == user, Router.status == "черновик")
        .order_by(Router.id_routers)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_first_published_id(db: AsyncSession):
    result = await db.execute(
        text(
            "SELECT id_routers FROM routers "
            "WHERE status = :status ORDER BY id_routers LIMIT 1"
        ),
        {"status": PUBLISHED},
    )
    return result.scalar()


async def get_next_published_id(db: AsyncSession, router_id: int):
    result = await db.execute(
        text(
            "SELECT id_routers FROM routers "
            "WHERE status = :status AND id_routers > :id "
            "ORDER BY id_routers LIMIT 1"
        ),
        {"status": PUBLISHED, "id": router_id},
    )
    return result.scalar()


@router.get("/")
async def root():
    return RedirectResponse(url="/feed")


@router.get("/feed")
async def get_feed(db: AsyncSession = Depends(get_db)):
    first_id = await get_first_published_id(db)
    if first_id is None:
        return RedirectResponse(url="/grid")
    return RedirectResponse(url=f"/feed/{first_id}")


@router.get("/feed/{router_id}")
async def get_feed_item(request: Request, router_id: int, db: AsyncSession = Depends(get_db)):
    current = await db.execute(
        text(
            "SELECT * FROM routers "
            "WHERE id_routers = :id AND status = :status LIMIT 1"
        ),
        {"id": router_id, "status": PUBLISHED},
    )
    router_row = current.mappings().first()

    if router_row is None:
        first_id = await get_first_published_id(db)
        if first_id is None:
            return RedirectResponse(url="/grid", status_code=303)
        return RedirectResponse(url=f"/feed/{first_id}", status_code=303)

    current_router = dict(router_row)

    next_id = await get_next_published_id(db, router_id)
    if next_id is None:
        next_id = await get_first_published_id(db)
    next_router = current_router if next_id is None else {**current_router, "id_routers": next_id}

    likes = await db.execute(
        text("SELECT COUNT(*) FROM likes WHERE id_routers = :id"),
        {"id": router_id},
    )
    current_router["likes"] = likes.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="tape.html",
        context={"router": current_router, "next_router": next_router},
    )


@router.get("/grid")
async def get_grid(
    request: Request,
    freq_min: float = Query(FREQ_MIN),
    freq_max: float = Query(FREQ_MAX),
    db: AsyncSession = Depends(get_db),
):
    low, high = sorted((freq_min, freq_max))

    stmt = (
        select(Router)
        .where(
            Router.status == PUBLISHED,
            Router.frequency >= low,
            Router.frequency <= high,
        )
        .order_by(Router.id_routers)
    )
    result = await db.execute(stmt)
    routers_list = result.scalars().all()

    like_counts = await db.execute(
        select(Likes.id_routers, func.count(Likes.id_routers)).group_by(Likes.id_routers)
    )
    likes_map = {row[0]: row[1] for row in like_counts.all()}

    return templates.TemplateResponse(
        request=request,
        name="tile.html",
        context={
            "routers_list": routers_list,
            "likes_map": likes_map,
            "freq_min": low,
            "freq_max": high,
        },
    )


@router.get("/add")
async def get_add_page(request: Request, db: AsyncSession = Depends(get_db)):
    draft = await get_draft(CURRENT_USER, db)
    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"draft": draft, "CURRENT_USER": CURRENT_USER},
    )


@router.post("/add")
async def add_draft(
    title: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    existing_draft = await get_draft(CURRENT_USER, db)
    if existing_draft is None:
        new_router = Router(
            title=title,
            creator=CURRENT_USER,
            status="черновик",
        )
        db.add(new_router)
        await db.commit()
    return RedirectResponse(url="/add", status_code=303)


@router.post("/publish")
async def publish_draft(
    description: str = Form(...),
    frequency: float = Form(...),
    standard: str = Form(""),
    max_speed: int | None = Form(None),
    antennas: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    draft = await get_draft(CURRENT_USER, db)
    if draft is not None:
        draft.standard = standard or None
        draft.max_speed = max_speed
        draft.description = description
        draft.frequency = frequency
        draft.band = f"{frequency} ГГц"
        draft.antennas = antennas or None
        draft.status = PUBLISHED
        draft.date_formed = datetime.now()
        await db.commit()
        return RedirectResponse(url=f"/feed/{draft.id_routers}", status_code=303)
    return RedirectResponse(url="/add", status_code=303)


@router.post("/routers/{router_id}/delete")
async def delete_router(router_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("UPDATE routers SET status = 'удален' WHERE id_routers = :id"),
        {"id": router_id},
    )
    await db.commit()
    return RedirectResponse(url="/grid", status_code=303)
