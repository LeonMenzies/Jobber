import os
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY: str = os.environ["CLAUDE_API_KEY"]
DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://jobber:jobber@db:5432/jobber")

SCRAPE_HOURS_OLD: int = int(os.environ.get("SCRAPE_HOURS_OLD", "48"))
SCRAPE_RESULTS_PER_TERM: int = int(os.environ.get("SCRAPE_RESULTS_PER_TERM", "30"))
SCRAPE_SCHEDULE_HOUR: int = int(os.environ.get("SCRAPE_SCHEDULE_HOUR", "7"))
SCRAPE_SCHEDULE_MINUTE: int = int(os.environ.get("SCRAPE_SCHEDULE_MINUTE", "0"))

APP_TIMEZONE: str = os.environ.get("APP_TIMEZONE", "America/Vancouver")

SEARCH_TERMS: list[str] = [
    "software developer",
    "software engineer",
    "full stack developer",
    "full stack engineer",
    "web developer",
    "backend developer",
    "frontend developer",
]

SEARCH_LOCATION: str = "Vancouver, BC, Canada"

# Exclude fully remote postings (on-site/hybrid only)
EXCLUDE_REMOTE: bool = True

# Title substrings that indicate a role is too junior or too senior — skip at ingest
EXCLUDED_TITLE_KEYWORDS: list[str] = [
    "junior",
    "jr.",
    " jr ",
    "entry level",
    "entry-level",
    "intern",
    "internship",
    "staff engineer",
    "principal engineer",
    "principal software",
    "distinguished engineer",
]
