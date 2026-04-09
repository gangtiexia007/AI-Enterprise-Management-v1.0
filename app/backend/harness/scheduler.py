import logging

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import Setting

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def _get_check_interval() -> int:
    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == "scheduler_interval_minutes").first()
        return int(s.value) if s else 30
    except Exception:
        return 30
    finally:
        db.close()


def _run_periodic_checks():
    """Execute rules engine checks within a fresh DB session."""
    from harness.rules_engine import check_overdue_tasks, check_escalations, calculate_kpi_scores

    db = SessionLocal()
    try:
        overdue = check_overdue_tasks(db)
        escalations = check_escalations(db)
        kpi = calculate_kpi_scores(db)
        logger.info(
            "Periodic check: %d overdue, %d escalations, %d KPI recalculated",
            overdue, escalations, kpi,
        )
    except Exception:
        logger.exception("Error in periodic check")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    interval = _get_check_interval()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_run_periodic_checks, "interval", minutes=interval, id="periodic_checks")
    _scheduler.start()
    logger.info("Scheduler started — running checks every %d minutes", interval)
