import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import ScrapeRun
import scheduler as sched
from scheduler import get_ranking_enabled, set_ranking_enabled

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_scrape_lock = threading.Lock()


@router.get("/scrape", response_class=HTMLResponse)
def scrape_page(request: Request, db: Session = Depends(get_db)):
    runs = (
        db.query(ScrapeRun)
        .order_by(ScrapeRun.started_at.desc())
        .limit(30)
        .all()
    )

    next_run = None
    job = sched.scheduler.get_job("daily_scrape")
    if job:
        next_run = job.next_run_time

    return templates.TemplateResponse(request, "scrape.html", {
        "runs": runs,
        "next_run": next_run,
        "is_running": not _scrape_lock.locked() is False,
        "ranking_enabled": get_ranking_enabled(),
    })


@router.post("/scrape/trigger")
def trigger_scrape():
    """Fire a manual scrape in a background thread."""
    if not _scrape_lock.acquire(blocking=False):
        return JSONResponse({"ok": False, "message": "Scrape already running"}, status_code=409)

    def _run():
        try:
            sched.run_all_scrapers()
        finally:
            _scrape_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return JSONResponse({"ok": True, "message": "Scrape started"})


@router.post("/scrape/rank")
def trigger_rank():
    """Trigger a ranking pass in background."""
    if not get_ranking_enabled():
        return JSONResponse({"ok": False, "message": "Ranking is disabled"}, status_code=409)

    def _run():
        from ranker import rank_unranked_jobs
        db = SessionLocal()
        try:
            rank_unranked_jobs(db, limit=200)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"ok": True, "message": "Ranking pass started"})


@router.post("/scrape/rank/toggle")
def toggle_ranking():
    enabled = not get_ranking_enabled()
    set_ranking_enabled(enabled)
    return JSONResponse({"ok": True, "enabled": enabled})


@router.get("/scrape/status")
def scrape_status(db: Session = Depends(get_db)):
    latest = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
    unranked = db.query(ScrapeRun).filter_by(status="running").count()
    return {
        "latest_run": {
            "status": latest.status if latest else None,
            "jobs_new": latest.jobs_new if latest else 0,
        } if latest else None,
        "active_scrapes": unranked,
    }
