"""APScheduler background refresh job."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from pricerator import config

log = logging.getLogger(__name__)

_PERIODIC_JOB_ID = "price-refresh-periodic"
_ONESHOT_JOB_ID = "price-refresh-oneshot"


def _run_refresh(app) -> None:
    from pricerator import refresh as _refresh
    with app.app_context():
        try:
            result = _refresh.refresh_all_prices()
            app.config["LAST_REFRESH_RESULT"] = result
        except Exception:
            log.exception("Background price refresh failed")


def start_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()
    _reschedule(scheduler, app)
    return scheduler


def _reschedule(scheduler: BackgroundScheduler, app) -> None:
    settings = config.load()
    hours = settings.refresh_hours()

    for job_id in (_PERIODIC_JOB_ID, _ONESHOT_JOB_ID):
        existing = scheduler.get_job(job_id)
        if existing:
            existing.remove()

    if hours is not None:
        scheduler.add_job(
            _run_refresh,
            "interval",
            hours=hours,
            id=_PERIODIC_JOB_ID,
            args=[app],
            misfire_grace_time=300,
        )
        log.info("Periodic price refresh scheduled every %dh", hours)


def trigger_oneshot(scheduler: BackgroundScheduler, app) -> None:
    existing = scheduler.get_job(_ONESHOT_JOB_ID)
    if existing:
        existing.remove()
    scheduler.add_job(
        _run_refresh,
        "date",
        id=_ONESHOT_JOB_ID,
        args=[app],
        replace_existing=True,
    )


def reschedule(scheduler: BackgroundScheduler, app) -> None:
    _reschedule(scheduler, app)
