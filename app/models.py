from datetime import datetime, timezone
from sqlalchemy import (Column, Integer, String, Text, Boolean,
                         DateTime, ARRAY, CheckConstraint)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    source = Column(String(60), nullable=False)
    url = Column(Text, nullable=False)
    url_fingerprint = Column(String(64), unique=True, nullable=False)
    title_company_fp = Column(String(64), index=True)

    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255))
    is_remote = Column(Boolean, default=False)
    is_hybrid = Column(Boolean, default=False)
    job_type = Column(String(50))
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(10))

    description_raw = Column(Text)

    posted_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    rank_score = Column(Integer)
    rank_summary = Column(Text)
    rank_match_reasons = Column(ARRAY(Text), default=list)
    rank_concerns = Column(ARRAY(Text), default=list)
    ranked_at = Column(DateTime(timezone=True))

    status = Column(String(20), default="new")
    user_notes = Column(Text)
    applied_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def score_label(self) -> str:
        if self.rank_score is None:
            return "Unranked"
        if self.rank_score >= 80:
            return "Great Match"
        if self.rank_score >= 60:
            return "Good Match"
        if self.rank_score >= 40:
            return "Maybe"
        return "Weak Match"

    @property
    def score_color(self) -> str:
        if self.rank_score is None:
            return "gray"
        if self.rank_score >= 80:
            return "green"
        if self.rank_score >= 60:
            return "blue"
        if self.rank_score >= 40:
            return "yellow"
        return "slate"

    @property
    def company_initial(self) -> str:
        return self.company[0].upper() if self.company else "?"

    def timeago(self) -> str:
        dt = self.posted_at or self.scraped_at
        if dt is None:
            return ""
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        days = diff.days
        if days > 30:
            return dt.strftime("%b %d")
        if days > 0:
            return f"{days}d ago"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        mins = diff.seconds // 60
        return f"{mins}m ago" if mins > 0 else "just now"


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True)
    resume_md = Column(Text)
    skills = Column(ARRAY(Text), default=list)
    target_roles = Column(ARRAY(Text), default=list)
    target_locations = Column(ARRAY(Text), default=list)
    experience_years = Column(Integer)
    notes = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def has_content(self) -> bool:
        return bool(self.resume_md and self.resume_md.strip())


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True)
    source = Column(String(60))
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True))
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_updated = Column(Integer, default=0)
    error_message = Column(Text)
    status = Column(String(20), default="running")

    def duration_str(self) -> str:
        if not self.finished_at:
            return "running…"
        delta = self.finished_at - self.started_at
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m {secs % 60}s"


class CompanyWatchlist(Base):
    __tablename__ = "company_watchlist"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    ats_type = Column(String(30), nullable=False)
    ats_slug = Column(String(255), nullable=False)
    active = Column(Boolean, default=True)
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
