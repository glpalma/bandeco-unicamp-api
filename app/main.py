import logging
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.config import settings
from app.database import create_db_and_tables
from app.routes.cardapio import router as cardapio_router
from app.tasks import run_scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Creating database tables")
    create_db_and_tables()

    logger.info(
        "Scheduling daily scrape at %02d:%02d (America/Sao_Paulo)",
        settings.scrape_hour,
        settings.scrape_minute,
    )
    scheduler.add_job(
        run_scrape,
        trigger=CronTrigger(
            hour=settings.scrape_hour,
            minute=settings.scrape_minute,
            timezone="America/Sao_Paulo",
        ),
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(
    title="Bandeco Unicamp API",
    description=(
        "REST API for the Unicamp university restaurant (bandeco) daily menu. "
        "Data is scraped daily from https://www.prefeitura.unicamp.br/cardapio/"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(cardapio_router)


@app.get("/", include_in_schema=False)
def root():
    return {"detail": "Bandeco Unicamp API. See /docs for interactive documentation."}


def run():
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
