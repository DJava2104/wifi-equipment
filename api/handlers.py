from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from data.collections import equipment_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
def get_feed(request: Request):
    return RedirectResponse(url="/feed/1")


@router.get("/feed/{eq_id}")
def get_feed_item(request: Request, eq_id: int):
    equipment = next((e for e in equipment_db if e["id"] == eq_id), None)
    if equipment is None:
        equipment = equipment_db[0]

    idx = equipment_db.index(equipment)
    next_equipment = equipment_db[(idx + 1) % len(equipment_db)]

    return templates.TemplateResponse(
        request=request,
        name="tape.html",
        context={"equipment": equipment, "next_equipment": next_equipment}
    )


@router.get("/grid")
def get_grid(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="tile.html",
        context={"equipment_list": equipment_db}
    )


@router.get("/add")
def get_add_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"equipment_list": equipment_db}
    )