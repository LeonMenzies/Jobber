import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .base import BaseScraper
from models import CompanyWatchlist

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


class GreenhouseScraper(BaseScraper):
    source_name = "greenhouse"

    def fetch_jobs(self) -> list[dict[str, Any]]:
        companies: list[CompanyWatchlist] = (
            self.db.query(CompanyWatchlist)
            .filter_by(ats_type="greenhouse", active=True)
            .all()
        )
        if not companies:
            logger.info("[Greenhouse] No companies in watchlist — skipping")
            return []

        all_jobs: list[dict[str, Any]] = []
        with httpx.Client(timeout=20) as client:
            for company in companies:
                try:
                    url = GREENHOUSE_API.format(slug=company.ats_slug)
                    resp = client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    for job in data.get("jobs", []):
                        location = ""
                        offices = job.get("offices") or job.get("location", {})
                        if isinstance(offices, list) and offices:
                            location = offices[0].get("name", "")
                        elif isinstance(offices, dict):
                            location = offices.get("name", "")

                        # Filter to Vancouver-ish roles
                        loc_lower = location.lower()
                        if location and "vancouver" not in loc_lower and "remote" not in loc_lower and "canada" not in loc_lower:
                            continue

                        posted_at = None
                        raw_date = job.get("updated_at") or job.get("created_at")
                        if raw_date:
                            try:
                                posted_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                            except ValueError:
                                pass

                        all_jobs.append({
                            "url": job.get("absolute_url", ""),
                            "title": job.get("title", ""),
                            "company": company.name,
                            "location": location or "Vancouver, BC",
                            "is_remote": "remote" in loc_lower,
                            "is_hybrid": "hybrid" in loc_lower,
                            "description": job.get("content", ""),
                            "posted_at": posted_at,
                        })
                except Exception as exc:
                    logger.warning(f"[Greenhouse] Failed for {company.name}: {exc}")

        logger.info(f"[Greenhouse] Fetched {len(all_jobs)} jobs")
        return all_jobs
