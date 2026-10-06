from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from data.collections import equipment_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")

FREQ_MIN = 2.4
FREQ_MAX = 6.0


def ghz(value) -> str:
    """5.0 -> '5 ГГц', 2.4 -> '2.4 ГГц'."""
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


def get_published():
    """Удалённые и черновик в ленте и на плитке не показываются."""
    return [e for e in equipment_db if e["status"] == "опубликован"]


def with_likes(equipment):
    """Количество лайков вычисляется по коллекции ID пользователей."""
    return {**equipment, "like_count": len(equipment["likes"])}


@router.get("/")
def root():
    return RedirectResponse(url="/feed")


# Вкладка «Лента» открывается без ID — показывается первая опубликованная услуга.
# /feed/{id} — страница услуги, /feed/{id}?next=true — следующая после неё.
@router.get("/feed")
@router.get("/feed/{device_id}")
def get_feed(
    request: Request,
    device_id: int | None = None,
    go_next: bool = Query(False, alias="next"),
):
    published = get_published()
    if not published:
        return RedirectResponse(url="/grid")

    if device_id is None:
        index = 0
    else:
        index = next((i for i, e in enumerate(published) if e["id"] == device_id), None)
        if index is None:
            # услуга удалена, является черновиком или не существует
            return RedirectResponse(url="/feed")
        if go_next:
            index = (index + 1) % len(published)

    return templates.TemplateResponse(
        request=request,
        name="tape.html",
        context={"equipment": with_likes(published[index])},
    )


@router.get("/grid")
def get_grid(
    request: Request,
    freq_min: float = Query(FREQ_MIN),
    freq_max: float = Query(FREQ_MAX),
):
    low, high = sorted((freq_min, freq_max))
    equipment_list = [
        with_likes(e)
        for e in get_published()
        if low - 1e-9 <= e["band"] <= high + 1e-9
    ]

    return templates.TemplateResponse(
        request=request,
        name="tile.html",
        context={"equipment_list": equipment_list, "freq_min": low, "freq_max": high},
    )


# На странице добавления показывается единственная услуга в статусе «черновик».
@router.get("/add")
def get_add(request: Request):
    draft = next((e for e in equipment_db if e["status"] == "черновик"), None)
    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"draft": draft},
    )
