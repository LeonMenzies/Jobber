import json
import logging
from datetime import datetime, timezone

import anthropic
from sqlalchemy.orm import Session

import config
from models import Job, Profile

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
    return _client


def _build_prompt(job: Job, profile: Profile) -> str:
    profile_section = profile.resume_md.strip() if profile.resume_md else "(No profile provided — score based on role and location fit only)"

    salary_str = ""
    if job.salary_min or job.salary_max:
        parts = []
        if job.salary_min:
            parts.append(f"${job.salary_min:,}")
        if job.salary_max:
            parts.append(f"${job.salary_max:,}")
        currency = job.salary_currency or "CAD"
        salary_str = f"{' – '.join(parts)} {currency}"

    description = (job.description_raw or "")[:3000]

    return f"""You are helping a job seeker evaluate a job posting. Rate the job 0-100 for fit.

## Candidate Profile
{profile_section}

## Target
- Roles: Software Developer, Software Engineer, Full Stack Developer/Engineer
- Seniority: Intermediate or Senior (4 years experience — NOT junior, NOT staff/principal)
- Location: Vancouver, BC, Canada (on-site or hybrid — NOT fully remote)

## Job Posting
Title: {job.title}
Company: {job.company}
Location: {job.location or "Not specified"}
Type: {job.job_type or "Not specified"}
Remote: {"Yes" if job.is_remote else "Hybrid" if job.is_hybrid else "On-site"}
{f"Salary: {salary_str}" if salary_str else ""}

Description:
{description}

## Instructions
Return ONLY valid JSON, no explanation outside it:
{{
  "score": <integer 0-100>,
  "summary": "<one sentence — why this is or isn't a good fit>",
  "match_reasons": [<up to 3 short strings, strongest positives>],
  "concerns": [<up to 2 short strings, gaps or red flags>]
}}

Scoring guide:
- 80-100: Strong match on skills, location, seniority level, and role type
- 60-79: Good match with minor gaps
- 40-59: Partial match — worth reviewing
- 0-39: Poor fit — applies to: wrong location, wrong stack, irrelevant role, fully remote only, junior/entry-level, or staff/principal level (too senior)
"""


def rank_job(job: Job, profile: Profile) -> dict:
    """Call Claude to rank a single job. Returns parsed result dict."""
    prompt = _build_prompt(job, profile)
    client = _get_client()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def rank_unranked_jobs(db: Session, limit: int = 50) -> int:
    """Rank up to `limit` unranked jobs. Returns count ranked."""
    profile: Profile | None = db.query(Profile).filter_by(id=1).first()

    unranked = (
        db.query(Job)
        .filter(Job.rank_score.is_(None))
        .filter(Job.description_raw.isnot(None))
        .order_by(Job.scraped_at.desc())
        .limit(limit)
        .all()
    )

    if not unranked:
        logger.info("[Ranker] No unranked jobs to process")
        return 0

    if not profile or not profile.has_content:
        logger.info("[Ranker] No profile set — ranking with role/location heuristic only")

    ranked_count = 0
    for job in unranked:
        try:
            result = rank_job(job, profile or Profile())
            job.rank_score = max(0, min(100, int(result.get("score", 50))))
            job.rank_summary = result.get("summary", "")
            job.rank_match_reasons = result.get("match_reasons", [])
            job.rank_concerns = result.get("concerns", [])
            job.ranked_at = datetime.now(timezone.utc)
            db.commit()
            ranked_count += 1
            logger.info(f"[Ranker] {job.title} @ {job.company} → {job.rank_score}")
        except Exception as exc:
            logger.warning(f"[Ranker] Failed for job {job.id}: {exc}")
            db.rollback()
            continue

    logger.info(f"[Ranker] Ranked {ranked_count} jobs")
    return ranked_count
