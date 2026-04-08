"""
Background task: run scraper and upsert results into the database.
Kept in its own module so it can be called both by APScheduler and
the manual POST /cardapio/scrape endpoint.
"""

import logging
from typing import Callable
from datetime import datetime
from sqlmodel import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import BRASILIA_TZ
from app.database import engine
from app.models import Cardapio
from app.scraper import scrape_cardapio

logger = logging.getLogger(__name__)

def _get_insert_func() -> Callable:
    if engine.dialect.name == "postgresql":
        return pg_insert
    return sqlite_insert

async def run_scrape() -> None:
    """Scrape the Unicamp menu page and upsert all found entries into the database."""
    logger.info("Starting scrape job")
    try:
        records = await scrape_cardapio()
    except Exception as exc:
        logger.error("Scraping failed: %s", exc, exc_info=True)
        return

    if not records:
        logger.warning("Scrape returned no records")
        return

    now = datetime.now(BRASILIA_TZ)
    with Session(engine) as session:
        for rec in records:
            # Upsert: insert or update on unique constraint (works for both SQLite and PostgreSQL)
            stmt = (
                _get_insert_func()(Cardapio)
                .values(**rec, last_updated=now)
                .on_conflict_do_update(
                    index_elements=["data", "refeicao", "tipo"],
                    set_={
                        k: rec[k]
                        for k in [
                            "prato_principal",
                            "arroz_feijao",
                            "guarnicao",
                            "salada",
                            "sobremesa",
                            "suco",
                            "observacoes",
                        ]
                    }
                    | {"last_updated": now},
                )
            )
            session.exec(stmt)  # type: ignore[arg-type]
        session.commit()

    logger.info("Upserted %d records into the database", len(records))
