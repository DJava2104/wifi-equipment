from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, HTTPException
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


async def get_draft(user: str, db: AsyncSession):
    stmt = (
        select(Equipment)
        .where(Equipment.creator == user, Equipment.status == "черновик")
        .order_by(Equipment.id_equipment)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


@router.get("/")
async def root():
    return RedirectResponse(url="/feed/1")


@router.get("/feed/{eq_id}")
async def get_feed_item(request: Request, eq_id: int, db: AsyncSession = Depends(get_db)):
    current = await db.execute(
        text("SELECT * FROM equipment WHERE id_equipment = :id AND status != 'удален' LIMIT 1"),
        {"id": eq_id},
    )
    equipment_row = current.mappings().first()

    if equipment_row is None:
        first = await db.execute(
            text("SELECT id_equipment FROM equipment WHERE status != 'удален' ORDER BY id_equipment LIMIT 1")
        )
        first_id = first.scalar()
        if first_id is None:
            raise HTTPException(status_code=404, detail="Услуги не найдены")
        return RedirectResponse(url=f"/feed/{first_id}", status_code=303)

    equipment = dict(equipment_row)

    nxt = await db.execute(
        text(
            "SELECT id_equipment FROM equipment "
            "WHERE status != 'удален' AND id_equipment > :id "
            "ORDER BY id_equipment LIMIT 1"
        ),
        {"id": eq_id},
    )
    next_id = nxt.scalar()
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
async def get_grid(request: Request, search: str = "", db: AsyncSession = Depends(get_db)):
    stmt = select(Equipment).where(Equipment.status != "удален")
    if search:
        stmt = stmt.where(Equipment.title.ilike(f"%{search}%"))
    stmt = stmt.order_by(Equipment.id_equipment)

    result = await db.execute(stmt)
    equipment_list = result.scalars().all()

    like_counts = await db.execute(
        select(Likes.id_equipment, func.count(Likes.id_equipment)).group_by(Likes.id_equipment)
    )
    likes_map = {row[0]: row[1] for row in like_counts.all()}

    return templates.TemplateResponse(
        request=request,
        name="tile.html",
        context={"equipment_list": equipment_list, "likes_map": likes_map, "search": search},
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
        new_equipment = Equipment(
            title=title,
            creator=CURRENT_USER,
            status="черновик",
        )
        db.add(new_equipment)
        await db.commit()
    return RedirectResponse(url="/add", status_code=303)


@router.post("/publish")
async def publish_draft(
    description: str = Form(...),
    standard: str = Form(...),
    max_speed: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    draft = await get_draft(CURRENT_USER, db)
    if draft is not None:
        draft.description = description
        draft.standard = standard
        draft.max_speed = max_speed
        draft.status = "опубликован"
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