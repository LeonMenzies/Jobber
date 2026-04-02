import json
import logging
import re
from datetime import datetime, timezone

import anthropic
from sqlalchemy.orm import Session

import config
from models import Job, Profile

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None

# Boilerplate patterns stripped from descriptions before ranking
_BOILERPLATE_PATTERNS = [
    re.compile(r'equal opportunity employer[^\n]*', re.IGNORECASE),
    re.compile(r'we are an equal[^\n]*', re.IGNORECASE),
    re.compile(r'eoe[^\n]*', re.IGNORECASE),
    re.compile(r'disability[^\n]*accommodation[^\n]*', re.IGNORECASE),
    re.compile(r'(our\s+)?benefits\s+(include|package|we offer)[^.]*\.', re.IGNORECASE),
    re.compile(r'competitive (salary|compensation|pay)[^\n]*', re.IGNORECASE),
    re.compile(r'we offer[^\n]*benefits[^\n]*', re.IGNORECASE),
    re.compile(r'health\s*(and\s*dental)?\s*insurance[^\n]*', re.IGNORECASE),
    re.compile(r'(rrsp|401k|retirement)[^\n]*', re.IGNORECASE),
    re.compile(r'paid\s+time\s+off[^\n]*', re.IGNORECASE),
]


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
    return _client


def _trim_description(raw: str) -> str:
    """Remove boilerplate and cap description at 1,500 chars."""
    text = raw or ""
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
    # Collapse runs of blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()[:1500]


def _build_ranker_profile(profile: Profile) -> str:
    """Build a compact ~150-token profile summary for ranking calls."""
    if not profile or not profile.has_content:
        return "(No profile — score based on role and location fit only)"

    lines = []

    # Extract skills from resume if not set separately
    if profile.skills:
        lines.append(f"Skills: {', '.join(profile.skills)}")
    else:
        # Pull first skills line from resume as a fallback hint
        if profile.resume_md:
            for line in profile.resume_md.splitlines():
                if "skill" in line.lower() or ":" in line:
                    snippet = line.strip().lstrip("#-* ")
                    if len(snippet) > 10:
                        lines.append(f"Skills (from resume): {snippet[:200]}")
                        break

    exp = profile.experience_years
    if exp:
        lines.append(f"Experience: {exp} years")

    if profile.target_roles:
        lines.append(f"Target roles: {', '.join(profile.target_roles)}")

    if profile.seniority_levels:
        lines.append(f"Seniority: {', '.join(profile.seniority_levels)}")
    else:
        lines.append("Seniority: Intermediate or Senior (NOT junior, NOT staff/principal)")

    if profile.work_arrangement:
        lines.append(f"Work arrangement: {', '.join(profile.work_arrangement)}")
    else:
        lines.append("Work arrangement: On-site or Hybrid (NOT fully remote)")

    if profile.target_locations:
        lines.append(f"Location: {', '.join(profile.target_locations)}")
    else:
        lines.append("Location: Vancouver, BC, Canada")

    if profile.preferred_industries:
        lines.append(f"Preferred industries: {', '.join(profile.preferred_industries)}")

    if profile.excluded_industries:
        lines.append(f"Excluded industries: {', '.join(profile.excluded_industries)}")

    if profile.company_sizes:
        lines.append(f"Company size preference: {', '.join(profile.company_sizes)}")

    if profile.salary_min_cad:
        lines.append(f"Min salary: ${profile.salary_min_cad:,} CAD")

    if profile.tech_stack_preferences:
        lines.append(f"Preferred stack: {', '.join(profile.tech_stack_preferences)}")

    if profile.open_to_contract:
        lines.append("Open to contract: Yes")
    else:
        lines.append("Open to contract: No (full-time only)")

    if profile.excluded_companies:
        lines.append(f"Excluded companies: {', '.join(profile.excluded_companies)}")

    if profile.notes:
        lines.append(f"Additional notes: {profile.notes[:300]}")

    return "\n".join(lines)


def _haiku_prefilter(job: Job, client: anthropic.Anthropic) -> bool:
    """
    Fast haiku check: returns True if job should be passed to Sonnet for full ranking,
    False if it's clearly a skip (wrong location / fully remote only / obviously wrong role).
    """
    location_str = job.location or "Not specified"
    remote_str = "fully remote" if job.is_remote and not job.is_hybrid else "on-site/hybrid possible"

    response = client.messages.create(
        model="claude-haiku-3-5",
        max_tokens=10,
        system="Answer only YES or NO.",
        messages=[{
            "role": "user",
            "content": (
                f"Is this job worth reviewing for a Vancouver, BC software engineer who wants on-site or hybrid work?\n"
                f"Title: {job.title}\n"
                f"Company: {job.company}\n"
                f"Location: {location_str}\n"
                f"Work type: {remote_str}\n"
                f"Answer YES if it could be a match, NO if it's clearly remote-only, wrong location, or irrelevant role."
            ),
        }],
    )
    answer = response.content[0].text.strip().upper()
    return answer.startswith("Y")


def _build_prompt(job: Job, ranker_profile: str) -> tuple[str, str]:
    """Build (system_prompt, user_message) for the Sonnet ranking call."""
    salary_str = ""
    if job.salary_min or job.salary_max:
        parts = []
        if job.salary_min:
            parts.append(f"${job.salary_min:,}")
        if job.salary_max:
            parts.append(f"${job.salary_max:,}")
        currency = job.salary_currency or "CAD"
        salary_str = f"{' – '.join(parts)} {currency}"

    description = _trim_description(job.description_raw or "")

    system = (
        "You are a job-fit evaluator. Rate the job 0-100 for fit with the candidate. "
        "Return ONLY valid JSON: {\"score\":<int>,\"summary\":\"<one sentence>\","
        "\"match_reasons\":[<up to 3 strings>],\"concerns\":[<up to 2 strings>]}"
    )

    user = (
        f"## Candidate\n{ranker_profile}\n\n"
        f"## Job\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location or 'Not specified'}\n"
        f"Type: {job.job_type or 'Not specified'} | "
        f"{'Remote' if job.is_remote else 'Hybrid' if job.is_hybrid else 'On-site'}\n"
        + (f"Salary: {salary_str}\n" if salary_str else "")
        + f"\n{description}"
    )

    return system, user


def rank_job(job: Job, ranker_profile: str) -> dict:
    """Call Claude Sonnet to rank a single job. Returns parsed result dict."""
    system, user = _build_prompt(job, ranker_profile)
    client = _get_client()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    raw = response.content[0].text.strip()
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

    # Build compact profile once for the whole batch
    ranker_profile = _build_ranker_profile(profile or Profile())
    client = _get_client()

    ranked_count = 0
    skipped_count = 0
    for job in unranked:
        try:
            # Haiku pre-filter: skip clearly irrelevant jobs without a Sonnet call
            if not _haiku_prefilter(job, client):
                job.rank_score = 5
                job.rank_summary = "Pre-filtered: clearly not a match (wrong location/type/role)."
                job.rank_match_reasons = []
                job.rank_concerns = ["Auto-skipped by location/type pre-filter"]
                job.ranked_at = datetime.now(timezone.utc)
                db.commit()
                skipped_count += 1
                logger.info(f"[Ranker] PRE-FILTER skip: {job.title} @ {job.company}")
                continue

            result = rank_job(job, ranker_profile)
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

    logger.info(f"[Ranker] Ranked {ranked_count} jobs, pre-filtered {skipped_count}")
    return ranked_count + skipped_count
