import json
import logging

import anthropic

import config
from models import Job, Profile

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None

_DEFAULT_PROFILE = (
    "Software Engineer with 4+ years experience across PHP, Python, Node.js, React, "
    "TypeScript, AWS, Docker, PostgreSQL, MySQL. Currently at VoPay International "
    "(fintech/payments). Previously Full Stack Developer at New Zealand Exchange. "
    "BSc Computer Science, GPA 3.86/4. Based in Vancouver, BC."
)


def _build_prompt(job: Job, profile: Profile) -> str:
    profile_section = (
        profile.resume_md.strip()
        if (profile and profile.resume_md)
        else _DEFAULT_PROFILE
    )
    description = (job.description_raw or "")[:5000]
    salary_str = ""
    if job.salary_min or job.salary_max:
        parts = []
        if job.salary_min:
            parts.append(f"${job.salary_min:,}")
        if job.salary_max:
            parts.append(f"${job.salary_max:,}")
        salary_str = f"Salary: {' – '.join(parts)} {job.salary_currency or 'CAD'}"

    return f"""You are tailoring Leon Menzies' resume for a specific job application.

## Leon's Full Profile
{profile_section}

## Target Role
Title: {job.title}
Company: {job.company}
Location: {job.location or "Vancouver, BC"}
{salary_str}
Job Description:
{description}

## Instructions

Generate tailored resume content. Keep bullets concise — max 12 words each, impact-first.

Rules:
- vopay_bullets: 3–4 bullets for his Software Engineer role at VoPay International (fintech). Lead with what he built/shipped, quantify if possible.
- nzx_dev_bullets: 2–3 bullets for his Full Stack Developer role at NZX. Focus on what's most relevant to this specific role.
- nzx_intern_bullets: 1 bullet for his Tester Intern role at NZX. Keep it brief.
- summary: 2 sentences max. Specific to this role. No "passionate about" or generic filler. Sound like a real person.
- highlighted_skills: ordered list of the 12–16 most relevant skills for THIS specific role, from Leon's background. Put the most role-relevant ones first.

Return ONLY valid JSON:
{{
  "summary": "string",
  "vopay_bullets": ["string", "string", "string"],
  "nzx_dev_bullets": ["string", "string"],
  "nzx_intern_bullets": ["string"],
  "highlighted_skills": ["skill1", "skill2", "skill3"]
}}
"""


def generate_resume(job: Job, profile: Profile | None) -> dict:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    prompt = _build_prompt(job, profile or Profile())
    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
