import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import scheduler
from database import engine
from models import Base
from routers import jobs, profile, scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (init.sql handles it on first boot, this is a safety net)
    Base.metadata.create_all(bind=engine)
    scheduler.start()
    logger.info("Jobber started — scheduler running")
    yield
    scheduler.stop()
    logger.info("Jobber stopped")


app = FastAPI(title="Jobber", lifespan=lifespan)

templates = Jinja2Templates(directory="templates")

app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(scrape.router)
