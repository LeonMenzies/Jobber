# Jobber — Job Search Aggregator & Ranker

> **Build status: ✅ COMPLETE — ready to run**
> Port: **3008** | Last updated: 2026-03-23

## How to Run

```bash
cd /home/lenny/apps/Jobber

# 1. Create your .env file
cp .env.example .env
# Edit .env and set CLAUDE_API_KEY=your-key

# 2. Build and start
docker compose up -d --build

# 3. Open in browser
# http://localhost:3008

# 4. Trigger first scrape (or wait for 7am daily run)
# Go to http://localhost:3008/scrape → click "Run Now"
```

## Overview

A Dockerized personal job-search assistant that scrapes multiple job boards daily, ranks listings against your profile/resume, and surfaces the best matches in a simple UI.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Docker Compose Stack                               │
│                                                     │
│  ┌──────────────┐   ┌──────────────┐               │
│  │  Scheduler   │   │   Web UI     │               │
│  │  (cron/APSc) │   │  (FastAPI +  │               │
│  └──────┬───────┘   │   HTMX/Jinja)│               │
│         │           └──────┬───────┘               │
│         ▼                  ▼                        │
│  ┌──────────────────────────────────┐              │
│  │         Core Python App          │              │
│  │  - Scraper Orchestrator          │              │
│  │  - AI Ranker (Claude API)        │              │
│  │  - Dedup / Normalizer            │              │
│  └──────────────┬───────────────────┘              │
│                 │                                   │
│  ┌──────────────▼───────────────────┐              │
│  │         PostgreSQL DB             │              │
│  │  - jobs, companies, applications  │              │
│  │  - user profile / resume         │              │
│  │  - rankings / scores             │              │
│  └──────────────────────────────────┘              │
└─────────────────────────────────────────────────────┘
```

---

## MCP Servers (Claude Code Dev Tooling)

These MCPs accelerate development and can also power the runtime AI ranking:

| MCP | Purpose |
|-----|---------|
| **jobspy-mcp-server** | Scrape Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google Jobs in one call |
| **Playwright MCP** | Scrape JS-heavy boards (Workday, Greenhouse, Lever) that block bots |
| **Firecrawl MCP** | Clean markdown extraction from job posting detail pages |
| **Shortlist MCP** | Direct ATS integrations (Ashby, Lever, SmartRecruiters, Greenhouse, Workday, Workable) |
| **SQLite / PostgreSQL MCP** | Query the local DB during dev/debugging |
| **Serper MCP** | Research companies, find Glassdoor reviews, news |

**Runtime** (inside Docker): The app calls Claude API directly for ranking — no MCP needed at runtime.

---

## Data Sources / Scrapers

Priority order (most signal → least noise):

1. **JobSpy** (Python lib) — Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google Jobs, Bayt
2. **Greenhouse / Lever / Ashby APIs** — public JSON feeds, no auth needed for many companies
3. **Workday scraper** — Playwright-based, targets specific company career pages
4. **LinkedIn Jobs API** (unofficial via JobSpy or direct)
5. **Hacker News "Who's Hiring"** — monthly thread parser
6. **Company career pages** — configurable list of target companies

---

## AI Ranking Pipeline

Each job gets scored 0–100 by Claude against your profile:

```
Job Posting
    │
    ▼
Normalizer  →  title, company, location, salary, remote, skills, description
    │
    ▼
Claude Ranker
    │  Input: normalized job + your resume + scoring criteria
    │  Output: { score, match_reasons[], dealbreakers[], suggested_angle }
    ▼
DB: jobs.rank_score, jobs.rank_reasoning
```

**Scoring dimensions (configurable weights):**
- Skills match %
- Seniority alignment
- Remote / location fit
- Salary range overlap
- Company size preference
- Industry fit
- Role type match (IC vs manager, etc.)

---

## Database Schema (PostgreSQL)

```sql
jobs          — id, source, external_id, title, company, location, remote,
                salary_min, salary_max, description_raw, description_md,
                posted_at, scraped_at, url, rank_score, rank_reasoning,
                status (new/reviewed/applied/rejected/archived)

companies     — id, name, domain, size, industry, glassdoor_rating, notes

applications  — id, job_id, applied_at, stage, notes, resume_version

profile       — resume_md, skills[], target_roles[], target_locations[],
                salary_min, remote_only, excluded_companies[], notes

scrape_runs   — id, source, started_at, finished_at, jobs_found, jobs_new, errors
```

---

## Web UI

Minimal, fast, keyboard-friendly. **FastAPI + HTMX + Tailwind** (or plain HTML).

**Views:**
- `/` — ranked job feed (today's new jobs, sorted by score)
- `/jobs/<id>` — full job detail + AI reasoning + one-click apply link
- `/applied` — application tracker (Kanban or table)
- `/profile` — edit resume/criteria/weights
- `/scrape` — trigger manual scrape, view scrape history

**Actions per job:**
- Mark as reviewed / applied / rejected / archived
- Add notes
- Copy tailored cover letter prompt to clipboard

---

## Daily Automation

```
06:00 UTC  →  run all scrapers
06:30 UTC  →  dedup + normalize
07:00 UTC  →  AI ranking pass on new jobs
07:30 UTC  →  (optional) email digest of top 10 new matches
```

Scheduler: **APScheduler** inside the app container, or a separate cron container.

---

## Docker Compose Services

```yaml
services:
  app:      # FastAPI + scheduler + scrapers
  db:       # PostgreSQL 16
  redis:    # (optional) task queue if scraping gets heavy
```

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Language | Python 3.12 | JobSpy, Playwright, Claude SDK all Python-native |
| Web | FastAPI + Jinja2 + HTMX | Fast, no JS build step needed |
| Scraping | JobSpy + Playwright | Covers 90% of boards |
| AI | Claude API (claude-sonnet-4-6) | Best instruction-following for structured ranking |
| DB | PostgreSQL | Robust, easy to query, good full-text search |
| Scheduler | APScheduler | No separate Celery/Redis needed for this scale |
| Container | Docker Compose | Per your requirement |

---

## Your Configuration

| Setting | Value |
|---------|-------|
| **Target roles** | Software Developer, Software Engineer, Full Stack Developer/Engineer |
| **Seniority** | Intermediate / Senior (4 years exp — excludes junior, staff, principal) |
| **Location** | Vancouver, BC, Canada — on-site or hybrid only (remote excluded) |
| **Salary** | No filter |
| **Company size** | Any |
| **Job boards** | All available — deduplicated by URL + title+company fingerprint |
| **Claude API** | API key via `.env` file |
| **Notifications** | None — browse daily on phone |
| **Scraping** | Free (Playwright-based, no paid services) |
| **UI** | Mobile-friendly, polished card layout |
| **Profile** | Pre-seeded with Leon Menzies resume (editable at /profile) |

---

## Deduplication Strategy

Jobs are considered duplicates if they share the same **canonical URL** OR the same **(company + normalized title)** posted within 7 days. Canonical URL is stored as the primary key; subsequent scrapers that find the same job update metadata but don't insert a new row.

---

## Mobile-First UI Design

Since the primary use is daily browsing on phone:
- **Card layout** — each job is a card with score badge, title, company, date, tags (remote/hybrid, location)
- **Score ring** — color-coded (green 80+, yellow 60-79, red <60)
- **Swipe-style actions** — reviewed / skip / save via large tap targets
- **Sticky filter bar** — filter by score, date, board, status without reloading
- **Dark mode** — easy on eyes, good for phone
- Tech: **FastAPI + Jinja2 + Tailwind CSS + Alpine.js** (tiny, no build step, reactive enough for filters/toggles)

---

## File Structure

```
Jobber/
├── PLAN.md
├── docker-compose.yml
├── .env.example              ← copy to .env, add CLAUDE_API_KEY
├── db/
│   └── init.sql              ← schema (auto-run on first boot)
└── app/
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py               ← FastAPI app + lifespan
    ├── config.py             ← settings from .env
    ├── database.py           ← SQLAlchemy engine + dedup fingerprinting
    ├── models.py             ← Job, Profile, ScrapeRun, CompanyWatchlist
    ├── ranker.py             ← Claude claude-sonnet-4-6 scoring pipeline
    ├── scheduler.py          ← APScheduler daily scrape at 7am Pacific
    ├── scrapers/
    │   ├── base.py           ← BaseScraper with upsert/dedup logic
    │   ├── jobspy_scraper.py ← Indeed/LinkedIn/Glassdoor/ZipRecruiter/Google
    │   ├── greenhouse.py     ← Public JSON API for company watchlist
    │   └── lever.py          ← Public JSON API for company watchlist
    ├── routers/
    │   ├── jobs.py           ← Feed, detail, status update endpoints
    │   ├── profile.py        ← Profile save + company watchlist CRUD
    │   └── scrape.py         ← Manual trigger + run history
    └── templates/
        ├── base.html         ← Dark theme, bottom nav, Tailwind + Alpine.js
        ├── index.html        ← Job feed with score cards + filters
        ├── job_detail.html   ← Full posting + AI analysis + actions
        ├── applied.html      ← Applied/saved tracker
        ├── profile.html      ← Resume input + company watchlist
        └── scrape.html       ← Run history + manual trigger
```

## Phased Delivery

### Phase 1 — Core ✅ DONE
- [x] Docker Compose setup (app + postgres)
- [x] JobSpy scraper (covers 5 boards: Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google)
- [x] DB schema + dedup logic (URL fingerprint + title/company fingerprint)
- [x] Claude ranking pipeline (claude-sonnet-4-6, scores 0-100)
- [x] Mobile-first dark UI (job cards, detail, filters, score badges)
- [x] Profile/criteria input page
- [x] Application tracker (saved/applied/rejected)
- [x] Daily scheduler (7am Pacific, APScheduler)

### Phase 2 — More Sources (optional)
- [ ] Playwright scraper for Workday career pages
- [ ] HN "Who's Hiring" monthly thread parser
- [ ] Ashby ATS scraper

### Phase 3 — Polish (optional)
- [x] Cover letter / tailoring prompt generator — **DONE** (applicator.py, AI-transparent angle baked in)
- [ ] Export applied jobs to CSV

---

*Last updated: 2026-03-23*
