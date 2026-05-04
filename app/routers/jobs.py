import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Job, Profile

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

VALID_STATUSES = {"new", "saved", "applied", "rejected", "archived"}
VALID_FILTERS = {"new", "saved", "applied", "rejected", "archived", "all"}


@router.get("/", response_class=HTMLResponse)
def feed(
    request: Request,
    status: str = "new",
    min_score: int | None = None,
    source: str | None = None,
    db: Session = Depends(get_db),
):
    if status not in VALID_FILTERS:
        status = "new"

    q = db.query(Job)
    if status != "all":
        q = q.filter(Job.status == status)
    if min_score is not None:
        q = q.filter(Job.rank_score >= min_score)
    if source:
        q = q.filter(Job.source == source)

    jobs = q.order_by(
        Job.rank_score.desc().nullslast(),
        Job.posted_at.desc().nullslast(),
    ).limit(200).all()

    # Stats for the filter bar
    counts = {}
    for s in ["new", "saved", "applied", "rejected"]:
        counts[s] = db.query(Job).filter(Job.status == s).count()
    counts["all"] = db.query(Job).count()

    # Available sources for filter
    sources = [r[0] for r in db.query(Job.source).distinct().order_by(Job.source).all()]

    return templates.TemplateResponse(request, "index.html", {
        "jobs": jobs,
        "active_status": status,
        "active_source": source or "",
        "min_score": min_score,
        "counts": counts,
        "sources": sources,
    })


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(request, "job_detail.html", {"job": job})


class StatusUpdate(BaseModel):
    status: str
    notes: str | None = None


@router.post("/jobs/{job_id}/status")
def update_status(job_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = body.status
    if body.notes is not None:
        job.user_notes = body.notes
    if body.status == "applied":
        from datetime import datetime, timezone
        job.applied_at = datetime.now(timezone.utc)

    db.commit()
    return {"ok": True, "status": job.status}


@router.get("/jobs/{job_id}/resume", response_class=HTMLResponse)
def resume_page(request: Request, job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = db.query(Profile).filter_by(id=1).first()
    from resume_generator import generate_resume
    try:
        resume = generate_resume(job, profile)
    except Exception as exc:
        logger.error(f"[ResumeGenerator] Failed for job {job_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Resume generation failed: {exc}")

    ai_setup_notes = getattr(profile, "ai_setup_notes", None) or ""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return templates.TemplateResponse(request, "resume.html", {
        "job": job,
        "resume": resume,
        "ai_setup_notes": ai_setup_notes,
        "generated_at": generated_at,
    })


@router.post("/jobs/{job_id}/generate-application")
def generate_application(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    from applicator import generate_application as _generate
    profile = db.query(Profile).filter_by(id=1).first()
    try:
        result = _generate(job, profile)
        return result
    except Exception as exc:
        logger.error(f"[Applicator] Failed for job {job_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/applied", response_class=HTMLResponse)
def applied(request: Request, db: Session = Depends(get_db)):
    jobs = (
        db.query(Job)
        .filter(Job.status == "applied")
        .order_by(Job.applied_at.desc().nullslast())
        .all()
    )
    saved = (
        db.query(Job)
        .filter(Job.status == "saved")
        .order_by(Job.rank_score.desc().nullslast())
        .all()
    )
    return templates.TemplateResponse(request, "applied.html", {
        "applied_jobs": jobs,
        "saved_jobs": saved,
    })
