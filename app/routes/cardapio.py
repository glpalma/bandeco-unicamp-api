from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.config import BRASILIA_TZ
from app.database import get_session
from app.tasks import run_scrape
from app.models import (
    Cardapio,
    CardapioResponse,
    DatasDisponiveisResponse,
    ItemRefeicao,
    RefeicaoResponse,
)

router = APIRouter(prefix="/cardapio", tags=["cardapio"])


def _build_response(rows: list[Cardapio], menu_date: date) -> CardapioResponse:
    """Assemble a CardapioResponse from a flat list of DB rows for one date."""
    almoco_regular: ItemRefeicao | None = None
    almoco_vegano: ItemRefeicao | None = None
    jantar_regular: ItemRefeicao | None = None
    jantar_vegano: ItemRefeicao | None = None
    last_updated: datetime = max(
        (r.last_updated for r in rows),
        default=datetime.now(BRASILIA_TZ),
    )

    for row in rows:
        item = ItemRefeicao(
            prato_principal=row.prato_principal,
            arroz_feijao=row.arroz_feijao,
            guarnicao=row.guarnicao,
            salada=row.salada,
            sobremesa=row.sobremesa,
            suco=row.suco,
            observacoes=row.observacoes,
        )
        if row.refeicao == "almoco" and row.tipo == "regular":
            almoco_regular = item
        elif row.refeicao == "almoco" and row.tipo == "vegano":
            almoco_vegano = item
        elif row.refeicao == "jantar" and row.tipo == "regular":
            jantar_regular = item
        elif row.refeicao == "jantar" and row.tipo == "vegano":
            jantar_vegano = item

    almoco = RefeicaoResponse(regular=almoco_regular, vegano=almoco_vegano) \
        if (almoco_regular or almoco_vegano) else None
    jantar = RefeicaoResponse(regular=jantar_regular, vegano=jantar_vegano) \
        if (jantar_regular or jantar_vegano) else None

    return CardapioResponse(data=menu_date, last_updated=last_updated, almoco=almoco, jantar=jantar)


@router.get("/", response_model=DatasDisponiveisResponse)
def list_available_dates(session: Session = Depends(get_session)):
    """Return all dates that have at least one scraped menu entry."""
    rows = session.exec(select(Cardapio.data).distinct().order_by(Cardapio.data)).all()
    return DatasDisponiveisResponse(datas=list(rows))

@router.post("/scrape", status_code=202)
async def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Manually trigger a scraping run in the background.
    Returns immediately with 202 Accepted; results will be available shortly.
    """
    background_tasks.add_task(run_scrape)
    return {"detail": "Scraping started in the background."}


@router.get("/{data}", response_model=CardapioResponse)
def get_cardapio(data: date, session: Session = Depends(get_session)):
    """
    Return the full menu for a given date (format: YYYY-MM-DD).
    Includes almoço and jantar, each with regular and vegano options when available.
    """
    rows = session.exec(
        select(Cardapio).where(Cardapio.data == data)
    ).all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No menu found for {data}. "
                   "Try POST /cardapio/scrape to fetch the latest data.",
        )

    return _build_response(list(rows), data)
