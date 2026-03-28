from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Profile, CompanyWatchlist

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter_by(id=1).first()
    watchlist = db.query(CompanyWatchlist).order_by(CompanyWatchlist.name).all()
    return templates.TemplateResponse(request, "profile.html", {
        "profile": profile,
        "watchlist": watchlist,
        "saved": request.query_params.get("saved") == "1",
    })


@router.post("/profile")
def save_profile(
    request: Request,
    resume_md: str = Form(""),
    experience_years: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter_by(id=1).first()
    if not profile:
        profile = Profile(id=1)
        db.add(profile)

    profile.resume_md = resume_md.strip() or None
    try:
        profile.experience_years = int(experience_years) if experience_years.strip() else None
    except ValueError:
        profile.experience_years = None
    profile.notes = notes.strip() or None
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/watchlist/add")
def add_watchlist(
    name: str = Form(...),
    ats_type: str = Form(...),
    ats_slug: str = Form(...),
    db: Session = Depends(get_db),
):
    entry = CompanyWatchlist(name=name.strip(), ats_type=ats_type, ats_slug=ats_slug.strip())
    db.add(entry)
    db.commit()
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/watchlist/{entry_id}/delete")
def delete_watchlist(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(CompanyWatchlist).filter_by(id=entry_id).first()
    if entry:
        db.delete(entry)
        db.commit()
    return RedirectResponse("/profile?saved=1", status_code=303)
