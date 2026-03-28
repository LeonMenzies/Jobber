import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Fingerprinting ──────────────────────────────────────────────────────────

_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "ref", "source", "via", "trk", "referer",
                    "tracking_id", "sid"}

def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        params = parse_qs(p.query, keep_blank_values=False)
        clean = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
        clean_query = urlencode(clean, doseq=True)
        return urlunparse(p._replace(query=clean_query, fragment="", scheme=p.scheme.lower()))
    except Exception:
        return url


def make_url_fingerprint(url: str) -> str:
    normalized = _normalize_url(url).lower().rstrip("/")
    return hashlib.sha256(normalized.encode()).hexdigest()[:48]


def _normalize_text(text: str) -> str:
    text = text.lower()
    # Remove seniority words that create false non-duplicates
    text = re.sub(r"\b(senior|junior|mid|lead|principal|staff|sr|jr|associate|entry.?level)\.?\s*", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_title_company_fingerprint(title: str, company: str) -> str:
    combined = _normalize_text(title) + " " + _normalize_text(company)
    return hashlib.sha256(combined.encode()).hexdigest()[:48]
