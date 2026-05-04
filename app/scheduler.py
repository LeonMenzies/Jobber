import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database import SessionLocal
from scrapers import JobSpyScraper, GreenhouseScraper, LeverScraper
from ranker import rank_unranked_jobs

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=config.APP_TIMEZONE)

_ranking_enabled: bool = True


def get_ranking_enabled() -> bool:
    return _ranking_enabled


def set_ranking_enabled(value: bool) -> None:
    global _ranking_enabled
    _ranking_enabled = value
    logger.info(f"[Scheduler] Ranking {'enabled' if value else 'disabled'}")


def run_all_scrapers():
    logger.info("[Scheduler] Starting daily scrape run")
    db = SessionLocal()
    try:
        for ScraperClass in [JobSpyScraper, GreenhouseScraper, LeverScraper]:
            try:
                scraper = ScraperClass(db)
                run = scraper.run()
                logger.info(
                    f"[Scheduler] {ScraperClass.source_name}: "
                    f"{run.jobs_new} new, {run.jobs_updated} updated"
                )
            except Exception as exc:
                logger.error(f"[Scheduler] {ScraperClass.source_name} failed: {exc}")
    finally:
        db.close()

    if _ranking_enabled:
        logger.info("[Scheduler] Scrape complete — starting ranking pass")
        run_ranking_pass()
    else:
        logger.info("[Scheduler] Scrape complete — ranking is disabled, skipping")


def run_ranking_pass():
    logger.info("[Scheduler] Starting ranking pass")
    db = SessionLocal()
    try:
        count = rank_unranked_jobs(db, limit=100)
        logger.info(f"[Scheduler] Ranking complete: {count} jobs ranked")
    except Exception as exc:
        logger.error(f"[Scheduler] Ranking failed: {exc}")
    finally:
        db.close()


def start():
    scheduler.add_job(
        run_all_scrapers,
        trigger=CronTrigger(
            hour=config.SCRAPE_SCHEDULE_HOUR,
            minute=config.SCRAPE_SCHEDULE_MINUTE,
            timezone=config.APP_TIMEZONE,
        ),
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"[Scheduler] Started — daily scrape at "
        f"{config.SCRAPE_SCHEDULE_HOUR:02d}:{config.SCRAPE_SCHEDULE_MINUTE:02d} {config.APP_TIMEZONE}"
    )


def stop():
    if scheduler.running:
        scheduler.shutdown(wait=False)
