import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .base import BaseScraper
from models import CompanyWatchlist

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"


class LeverScraper(BaseScraper):
    source_name = "lever"

    def fetch_jobs(self) -> list[dict[str, Any]]:
        companies: list[CompanyWatchlist] = (
            self.db.query(CompanyWatchlist)
            .filter_by(ats_type="lever", active=True)
            .all()
        )
        if not companies:
            logger.info("[Lever] No companies in watchlist — skipping")
            return []

        all_jobs: list[dict[str, Any]] = []
        with httpx.Client(timeout=20) as client:
            for company in companies:
                try:
                    url = LEVER_API.format(slug=company.ats_slug)
                    resp = client.get(url)
                    resp.raise_for_status()
                    postings = resp.json()

                    for job in postings:
                        location = (job.get("categories") or {}).get("location", "")
                        loc_lower = location.lower()

                        if location and "vancouver" not in loc_lower and "remote" not in loc_lower and "canada" not in loc_lower:
                            continue

                        posted_ms = job.get("createdAt")
                        posted_at = None
                        if posted_ms:
                            try:
                                posted_at = datetime.fromtimestamp(posted_ms / 1000, tz=timezone.utc)
                            except (ValueError, OSError):
                                pass

                        # Build plain-text description from lists
                        desc_parts = []
                        for section in (job.get("lists") or []):
                            desc_parts.append(section.get("text", ""))
                            desc_parts.append(section.get("content", ""))
                        description = "\n\n".join(p for p in desc_parts if p).strip()

                        all_jobs.append({
                            "url": job.get("hostedUrl", ""),
                            "title": job.get("text", ""),
                            "company": company.name,
                            "location": location or "Vancouver, BC",
                            "is_remote": "remote" in loc_lower,
                            "is_hybrid": "hybrid" in loc_lower,
                            "description": description or None,
                            "posted_at": posted_at,
                        })
                except Exception as exc:
                    logger.warning(f"[Lever] Failed for {company.name}: {exc}")

        logger.info(f"[Lever] Fetched {len(all_jobs)} jobs")
        return all_jobs
