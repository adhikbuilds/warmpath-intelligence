"""
APScheduler background jobs for periodic signal ingestion.

Daily:  job postings + funding news
Weekly: champion job change detection
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from routers.signals import _ingest_champion_changes, _ingest_funding_news, _ingest_job_postings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

WORKSPACE_ID = "default"  # In production: iterate over all active workspaces


def _daily_ingest() -> None:
    logger.info("[scheduler] Running daily signal ingestion")
    _ingest_job_postings(WORKSPACE_ID)
    _ingest_funding_news(WORKSPACE_ID)


def _weekly_ingest() -> None:
    logger.info("[scheduler] Running weekly champion change detection")
    _ingest_champion_changes(WORKSPACE_ID)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_daily_ingest, "cron", hour=6, minute=0, id="daily_ingest")
    _scheduler.add_job(_weekly_ingest, "cron", day_of_week="mon", hour=7, minute=0, id="weekly_champion")
    _scheduler.start()
    logger.info("[scheduler] Started daily@06:00, weekly champion@Mon 07:00")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Stopped")
