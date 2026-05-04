# Pipeline Plan — Profile Questionnaire + Ranker Efficiency

## Classification: feature

## Problem Summary

1. **Profile questionnaire**: The profile page only has a freeform resume textarea and notes field. A structured multi-select questionnaire would capture job-matching preferences more precisely and feed them into the ranker.

2. **Ranker token waste**: Currently, `ranker.py` sends up to 3,000 characters of raw job description plus the full resume markdown (which can be hundreds of lines) for every single job. That's 800–1,500 tokens input per call. With 50+ jobs to rank per run, this adds up quickly. The prompt also hard-codes Leon's preferences rather than reading from the profile, so changing preferences requires a code change.

---

## Part 1 — Profile Questionnaire

### New DB columns on `profile` table (migration via ALTER TABLE in init.sql + models.py)

| Column | Type | Purpose |
|---|---|---|
| `work_arrangement` | `TEXT[]` | e.g. ["on-site", "hybrid"] |
| `seniority_levels` | `TEXT[]` | e.g. ["intermediate", "senior"] |
| `preferred_industries` | `TEXT[]` | e.g. ["fintech", "saas", "gaming"] |
| `excluded_industries` | `TEXT[]` | e.g. ["banking", "gambling"] |
| `company_sizes` | `TEXT[]` | e.g. ["startup", "mid-size", "enterprise"] |
| `salary_min_cad` | `INTEGER` | Minimum acceptable salary |
| `tech_stack_preferences` | `TEXT[]` | e.g. ["python", "typescript", "react"] |
| `open_to_contract` | `BOOLEAN` | Whether contract/freelance roles are ok |
| `excluded_companies` | `TEXT[]` | Companies to auto-skip |

### Questionnaire questions (multi-select chips + a few inputs)

1. **Work arrangement** — On-site / Hybrid / Remote (multi-select)
2. **Seniority target** — Junior / Intermediate / Senior / Lead (multi-select)
3. **Company size preference** — Startup (<50) / Scale-up (50–200) / Mid-size (200–1k) / Enterprise (1k+) (multi-select)
4. **Preferred industries** — Fintech / SaaS / E-commerce / Gaming / Health-tech / AI/ML / Consulting / Government / Other (multi-select)
5. **Industries to avoid** — same options (multi-select)
6. **Tech stack preferences** — Python / TypeScript / JavaScript / React / Node.js / PHP / Ruby / Java / Go / Rust / AWS / GCP / Azure (multi-select)
7. **Open to contract roles?** — Yes / No (toggle)
8. **Minimum salary (CAD)** — number input
9. **Companies to exclude** — text list (comma-separated)

### UI
- New "Job Preferences" section on `/profile` page, above the resume textarea
- Mobile-first chip/pill multi-select using Alpine.js (no JavaScript build step)
- Chips are visually toggled on/off; selected values stored in hidden inputs as JSON arrays
- Submitted to existing `POST /profile` handler (extended to accept new fields)

---

## Part 2 — Ranker Efficiency + Accuracy

### Current problems
- Full resume (500+ tokens) sent every call — mostly static content
- Raw description truncated at 3,000 chars — often contains boilerplate/legal text that wastes tokens
- Scoring criteria hard-coded in prompt, not from profile fields
- `max_tokens=400` is fine but prompt itself is bloated
- No caching of the profile section across a batch run

### Fixes

#### A. Profile summary compression
- Pre-compute a compact "ranker profile" string at the start of each batch run instead of embedding full `resume_md` per-call
- The compact profile is a ~150-token structured summary: skills list, years exp, target roles, work arrangement, seniority, industry prefs/exclusions, company size, salary floor
- Generated once per `rank_unranked_jobs()` call, reused for all jobs in that batch
- The full resume is still available for the `applicator.py` (cover letter generation) — not touched

#### B. Description trimming
- Strip common boilerplate from `description_raw` before sending: "Equal Opportunity Employer", benefits paragraphs, legal disclaimers, "About us" sections longer than 200 chars
- Cap at 1,500 chars instead of 3,000 (the signal for matching is in the first half of most job postings)
- This alone cuts input tokens roughly in half per call

#### C. Dynamic scoring criteria from profile
- Replace the hard-coded target section in the prompt with fields read from the profile:
  - `target_roles`, `seniority_levels`, `work_arrangement`, `salary_min_cad`, `preferred_industries`, `excluded_industries`
- This makes ranking more accurate (actually reflects what user set) and removes stale hard-coded preferences

#### D. Use `claude-haiku-3-5` for pre-filtering (optional fast path)
- Before sending to Sonnet, run a fast haiku check: "Is this job in Vancouver or hybrid/on-site BC? Yes/No"
- Jobs that are clearly remote-only or wrong location get score=5 without a Sonnet call
- Saves ~30-40% of Sonnet calls based on typical job board noise
- This is additive — Sonnet is still used for all plausible matches

#### E. Prompt tightening
- Remove verbose scoring guide from prompt (Claude knows how to score 0-100)
- Tighten instructions to 3 lines
- Switch to a system prompt + short user message pattern (slightly cheaper on input tokens)

---

## Files to Change

| File | Change |
|---|---|
| `app/models.py` | Add 9 new columns to `Profile` |
| `db/init.sql` | Add ALTER TABLE migration block for new columns; update seed INSERT |
| `app/routers/profile.py` | Accept new form fields, parse multi-select JSON, save to profile |
| `app/templates/profile.html` | Add questionnaire section with Alpine.js chip selectors |
| `app/ranker.py` | Compact profile summary, description trimming, dynamic criteria, haiku pre-filter, tighter prompt |

---

## Out of Scope
- No changes to scrapers, scheduler, job detail page, or applied tracker
- No new DB tables
- No changes to applicator.py (cover letter — still uses full resume_md)

---

## Estimated Token Savings
- Before: ~900–1,400 input tokens per job
- After: ~300–500 input tokens per job (compact profile ~150t + trimmed description ~200t + prompt ~100t)
- Haiku pre-filter skips ~30% of calls entirely
- Net: ~60–70% reduction in Sonnet input tokens per ranking run
