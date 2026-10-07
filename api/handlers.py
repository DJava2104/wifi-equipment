from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.equipment import Equipment
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


def antennas_text(count) -> str:
    """Склонение: 1 антенна, 2-4 антенны, 5+ антенн."""
    count = int(count)
    if count % 10 == 1 and count % 100 != 11:
        word = "антенна"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        word = "антенны"
    else:
        word = "антенн"
    return f"{count} {word}"


templates.env.filters["ghz"] = ghz
templates.env.filters["antennas"] = antennas_text


async def get_draft(user: str, db: AsyncSession):
    stmt = (
        select(Equipment)
        .where(Equipment.creator == user, Equipment.status == "черновик")
        .order_by(Equipment.id_equipment)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_first_published_id(db: AsyncSession):
    result = await db.execute(
        text(
            "SELECT id_equipment FROM equipment "
            "WHERE status = :status ORDER BY id_equipment LIMIT 1"
        ),
        {"status": PUBLISHED},
    )
    return result.scalar()


async def get_next_published_id(db: AsyncSession, eq_id: int):
    result = await db.execute(
        text(
            "SELECT id_equipment FROM equipment "
            "WHERE status = :status AND id_equipment > :id "
            "ORDER BY id_equipment LIMIT 1"
        ),
        {"status": PUBLISHED, "id": eq_id},
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


@router.get("/feed/{eq_id}")
async def get_feed_item(request: Request, eq_id: int, db: AsyncSession = Depends(get_db)):
    current = await db.execute(
        text(
            "SELECT * FROM equipment "
            "WHERE id_equipment = :id AND status = :status LIMIT 1"
        ),
        {"id": eq_id, "status": PUBLISHED},
    )
    equipment_row = current.mappings().first()

    if equipment_row is None:
        first_id = await get_first_published_id(db)
        if first_id is None:
            return RedirectResponse(url="/grid", status_code=303)
        return RedirectResponse(url=f"/feed/{first_id}", status_code=303)

    equipment = dict(equipment_row)

    next_id = await get_next_published_id(db, eq_id)
    if next_id is None:
        next_id = await get_first_published_id(db)
    next_equipment = equipment if next_id is None else {**equipment, "id_equipment": next_id}

    likes = await db.execute(
        text("SELECT COUNT(*) FROM likes WHERE id_equipment = :id"),
        {"id": eq_id},
    )
    equipment["likes"] = likes.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="tape.html",
        context={"equipment": equipment, "next_equipment": next_equipment},
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
        select(Equipment)
        .where(
            Equipment.status == PUBLISHED,
            Equipment.frequency >= low,
            Equipment.frequency <= high,
        )
        .order_by(Equipment.id_equipment)
    )
    result = await db.execute(stmt)
    equipment_list = result.scalars().all()

    like_counts = await db.execute(
        select(Likes.id_equipment, func.count(Likes.id_equipment)).group_by(Likes.id_equipment)
    )
    likes_map = {row[0]: row[1] for row in like_counts.all()}

    return templates.TemplateResponse(
        request=request,
        name="tile.html",
        context={
            "equipment_list": equipment_list,
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
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    existing_draft = await get_draft(CURRENT_USER, db)
    if existing_draft is None:
        new_equipment = Equipment(
            title=title,
            description=description or None,
            creator=CURRENT_USER,
            status="черновик",
        )
        db.add(new_equipment)
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
        return RedirectResponse(url=f"/feed/{draft.id_equipment}", status_code=303)
    return RedirectResponse(url="/add", status_code=303)


@router.post("/equipment/{eq_id}/delete")
async def delete_equipment(eq_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("UPDATE equipment SET status = 'удален' WHERE id_equipment = :id"),
        {"id": eq_id},
    )
    await db.commit()
    return RedirectResponse(url="/grid", status_code=303)
