from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

import database
from models import Job, ScrapeRun


class BaseScraper(ABC):
    source_name: str = "unknown"

    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    def fetch_jobs(self) -> list[dict[str, Any]]:
        """Return list of raw job dicts from the source."""
        ...

    def run(self) -> ScrapeRun:
        run = ScrapeRun(source=self.source_name, status="running")
        self.db.add(run)
        self.db.commit()

        try:
            raw_jobs = self.fetch_jobs()
            run.jobs_found = len(raw_jobs)
            new_count = updated_count = 0

            for raw in raw_jobs:
                job, is_new = self._upsert(raw)
                if job:
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1

            run.jobs_new = new_count
            run.jobs_updated = updated_count
            run.status = "completed"
        except Exception as exc:
            run.error_message = str(exc)
            run.status = "failed"
            raise
        finally:
            run.finished_at = datetime.now(timezone.utc)
            self.db.commit()

        return run

    @staticmethod
    def _should_skip(raw: dict[str, Any]) -> bool:
        """Return True if the job should be dropped before storing."""
        if config.EXCLUDE_REMOTE and raw.get("is_remote"):
            return True
        title_lower = (raw.get("title") or "").lower()
        for kw in config.EXCLUDED_TITLE_KEYWORDS:
            if kw in title_lower:
                return True
        return False

    def _upsert(self, raw: dict[str, Any]) -> tuple[Job | None, bool]:
        """Insert or update a job. Returns (job, is_new)."""
        if self._should_skip(raw):
            return None, False

        url = raw.get("url", "").strip()
        if not url:
            return None, False

        url_fp = database.make_url_fingerprint(url)
        tc_fp = database.make_title_company_fingerprint(
            raw.get("title", ""), raw.get("company", "")
        )

        # 1. Exact URL match → update metadata only
        existing = self.db.query(Job).filter_by(url_fingerprint=url_fp).first()
        if existing:
            existing.description_raw = raw.get("description") or existing.description_raw
            existing.posted_at = raw.get("posted_at") or existing.posted_at
            self.db.commit()
            return existing, False

        # 2. Same title+company already from another board → skip
        if tc_fp:
            dupe = self.db.query(Job).filter_by(title_company_fp=tc_fp).first()
            if dupe:
                return dupe, False

        # 3. New job
        job = Job(
            source=self.source_name,
            url=url,
            url_fingerprint=url_fp,
            title_company_fp=tc_fp,
            title=raw.get("title", "Unknown Title"),
            company=raw.get("company", "Unknown Company"),
            location=raw.get("location"),
            is_remote=raw.get("is_remote", False),
            is_hybrid=raw.get("is_hybrid", False),
            job_type=raw.get("job_type"),
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            salary_currency=raw.get("salary_currency"),
            description_raw=raw.get("description"),
            posted_at=raw.get("posted_at"),
        )
        self.db.add(job)
        try:
            self.db.commit()
            return job, True
        except Exception:
            self.db.rollback()
            # Race condition — another worker inserted between our check and insert
            existing = self.db.query(Job).filter_by(url_fingerprint=url_fp).first()
            return existing, False
