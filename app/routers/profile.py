import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Profile, CompanyWatchlist

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _parse_array(value: str) -> list[str]:
    """Parse a JSON array string from a hidden input, returning [] on failure."""
    if not value or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if v]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


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
    work_arrangement: str = Form("[]"),
    seniority_levels: str = Form("[]"),
    preferred_industries: str = Form("[]"),
    excluded_industries: str = Form("[]"),
    company_sizes: str = Form("[]"),
    salary_min_cad: str = Form(""),
    tech_stack_preferences: str = Form("[]"),
    open_to_contract: str = Form("false"),
    excluded_companies: str = Form(""),
    ai_setup_notes: str = Form(""),
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

    profile.work_arrangement = _parse_array(work_arrangement)
    profile.seniority_levels = _parse_array(seniority_levels)
    profile.preferred_industries = _parse_array(preferred_industries)
    profile.excluded_industries = _parse_array(excluded_industries)
    profile.company_sizes = _parse_array(company_sizes)

    try:
        profile.salary_min_cad = int(salary_min_cad) if salary_min_cad.strip() else None
    except ValueError:
        profile.salary_min_cad = None

    profile.tech_stack_preferences = _parse_array(tech_stack_preferences)
    profile.open_to_contract = open_to_contract.lower() in ("true", "1", "yes", "on")

    # excluded_companies is submitted as comma-separated text
    if excluded_companies.strip():
        profile.excluded_companies = [c.strip() for c in excluded_companies.split(",") if c.strip()]
    else:
        profile.excluded_companies = []

    profile.ai_setup_notes = ai_setup_notes.strip() or None

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
