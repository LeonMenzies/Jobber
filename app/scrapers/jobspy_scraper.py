import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from jobspy import scrape_jobs

import config
from .base import BaseScraper

logger = logging.getLogger(__name__)

SITES = ["indeed", "linkedin", "glassdoor", "zip_recruiter", "google"]


class JobSpyScraper(BaseScraper):
    source_name = "jobspy"

    def fetch_jobs(self) -> list[dict[str, Any]]:
        all_jobs: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for term in config.SEARCH_TERMS:
            try:
                logger.info(f"[JobSpy] Scraping: {term!r} in {config.SEARCH_LOCATION}")
                df: pd.DataFrame = scrape_jobs(
                    site_name=SITES,
                    search_term=term,
                    location=config.SEARCH_LOCATION,
                    results_wanted=config.SCRAPE_RESULTS_PER_TERM,
                    hours_old=config.SCRAPE_HOURS_OLD,
                    country_indeed="Canada",
                    linkedin_fetch_description=True,
                    verbose=0,
                )
                if df.empty:
                    continue

                for _, row in df.iterrows():
                    url = str(row.get("job_url") or row.get("job_url_direct") or "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Parse date
                    posted_at = None
                    raw_date = row.get("date_posted")
                    if pd.notna(raw_date):
                        if isinstance(raw_date, datetime):
                            posted_at = raw_date.replace(tzinfo=timezone.utc) if raw_date.tzinfo is None else raw_date
                        else:
                            try:
                                posted_at = datetime.fromisoformat(str(raw_date)).replace(tzinfo=timezone.utc)
                            except ValueError:
                                pass

                    # Salary
                    salary_min = salary_max = None
                    salary_currency = None
                    if pd.notna(row.get("min_amount")):
                        try:
                            salary_min = int(float(row["min_amount"]))
                        except (ValueError, TypeError):
                            pass
                    if pd.notna(row.get("max_amount")):
                        try:
                            salary_max = int(float(row["max_amount"]))
                        except (ValueError, TypeError):
                            pass
                    if pd.notna(row.get("currency")):
                        salary_currency = str(row["currency"])

                    # Work type
                    is_remote = bool(row.get("is_remote", False))
                    location_str = str(row.get("location") or "")
                    is_hybrid = "hybrid" in location_str.lower() or "hybrid" in str(row.get("job_type") or "").lower()

                    job_type = str(row.get("job_type") or "").strip() or None

                    description = str(row.get("description") or "").strip() or None

                    source_site = str(row.get("site") or self.source_name)

                    all_jobs.append({
                        "url": url,
                        "title": str(row.get("title") or "").strip(),
                        "company": str(row.get("company") or "").strip(),
                        "location": location_str or config.SEARCH_LOCATION,
                        "is_remote": is_remote,
                        "is_hybrid": is_hybrid,
                        "job_type": job_type,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "salary_currency": salary_currency,
                        "description": description,
                        "posted_at": posted_at,
                        "source": f"jobspy_{source_site}",
                    })

            except Exception as exc:
                logger.warning(f"[JobSpy] Failed for term {term!r}: {exc}")
                continue

        logger.info(f"[JobSpy] Total unique jobs fetched: {len(all_jobs)}")
        return all_jobs

    def _upsert(self, raw: dict[str, Any]):
        # Override source_name per-job to preserve board name
        original = self.source_name
        self.source_name = raw.pop("source", self.source_name)
        result = super()._upsert(raw)
        self.source_name = original
        return result
