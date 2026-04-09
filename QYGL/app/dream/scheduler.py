"""Dream Scheduler — APScheduler 3.x setup for nightly and periodic jobs.

Schedule:
  - DB backup:             1:00 AM daily (7-day retention)
  - Memory distillation:   2:00 AM daily
  - Knowledge extraction:  3:00 AM daily
  - Daily reports:         6:00 AM daily
  - Weekly reports:        Sunday 6:00 AM
  - Monthly reports:       1st of month 6:00 AM
  - Overdue + progressive escalation: every 30 minutes
  - Approval expiry check: every 30 minutes
  - KPI auto-score (system): 23:00 daily
  - Anomaly detection:     9:00 AM daily
  - Retention alerts:      9:00 AM daily
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1},
        )
    return _scheduler


def setup_dream_scheduler(
    team_ids_provider: Any = None,
) -> BackgroundScheduler:
    """Configure and return the scheduler with all dream jobs.

    Args:
        team_ids_provider: Callable that returns a list of active team_ids.
                          Defaults to a function that queries the DB.
    """
    scheduler = get_scheduler()

    if team_ids_provider is None:
        team_ids_provider = _default_team_ids_provider

    scheduler.add_job(
        _run_db_backup,
        trigger=CronTrigger(hour=1, minute=0),
        id="db_backup",
        name="SQLite Backup (1:00 AM daily)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_distillation,
        trigger=CronTrigger(hour=2, minute=0),
        id="dream_distillation",
        name="Memory Distillation (2:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_knowledge_extraction,
        trigger=CronTrigger(hour=3, minute=0),
        id="dream_knowledge_extraction",
        name="Knowledge Extraction (3:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_daily_reports,
        trigger=CronTrigger(hour=6, minute=0),
        id="dream_daily_reports",
        name="Daily Reports (6:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_weekly_reports,
        trigger=CronTrigger(day_of_week="sun", hour=6, minute=0),
        id="dream_weekly_reports",
        name="Weekly Reports (Sunday 6:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_monthly_reports,
        trigger=CronTrigger(day=1, hour=6, minute=0),
        id="dream_monthly_reports",
        name="Monthly Reports (1st 6:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_escalation_automation,
        trigger=IntervalTrigger(minutes=30),
        id="escalation_automation",
        name="Overdue tasks + progressive escalation (every 30 min)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_kpi_auto_score,
        trigger=CronTrigger(hour=23, minute=0),
        id="kpi_auto_score",
        name="KPI system auto-score (23:00)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_anomaly_detection,
        trigger=CronTrigger(hour=9, minute=0),
        id="anomaly_detection",
        name="Anomaly detection (9:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_retention_alerts,
        trigger=CronTrigger(hour=9, minute=0),
        id="retention_alerts",
        name="Retention Alerts (9:00 AM)",
        replace_existing=True,
        kwargs={"team_ids_provider": team_ids_provider},
    )

    scheduler.add_job(
        _run_approval_expiry,
        trigger=IntervalTrigger(minutes=30),
        id="approval_expiry",
        name="Approval expiry check (every 30 min)",
        replace_existing=True,
    )

    logger.info("Dream scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Dream scheduler started")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Dream scheduler shut down")
    _scheduler = None


# ── Job implementations ───────────────────────────────────────────

def _run_db_backup() -> None:
    """Backup the SQLite database with 7-day retention."""
    import shutil
    from pathlib import Path
    from datetime import datetime, timedelta

    db_path = Path("data/qfbj.db")
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        logger.warning("DB backup skipped: %s not found", db_path)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"qfbj_{timestamp}.db"

    try:
        import sqlite3
        source = sqlite3.connect(str(db_path))
        dest = sqlite3.connect(str(backup_path))
        source.backup(dest)
        dest.close()
        source.close()
        logger.info("DB backup created: %s (%.1f MB)", backup_path, backup_path.stat().st_size / 1024 / 1024)
    except Exception:
        logger.error("DB backup failed", exc_info=True)
        return

    cutoff = datetime.now() - timedelta(days=7)
    for old_backup in sorted(backup_dir.glob("qfbj_*.db")):
        try:
            ts_str = old_backup.stem.replace("qfbj_", "")
            file_ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            if file_ts < cutoff:
                old_backup.unlink()
                logger.info("Old backup removed: %s", old_backup)
        except (ValueError, OSError):
            pass


def _run_distillation(team_ids_provider: Any) -> None:
    from app.dream.distiller import MemoryDistiller

    team_ids = team_ids_provider()
    distiller = MemoryDistiller()
    for tid in team_ids:
        try:
            distiller.distill_conversations(tid)
        except Exception:
            logger.error("Distillation failed for team %s", tid, exc_info=True)


def _run_daily_reports(team_ids_provider: Any) -> None:
    from app.dream.reporter import ReportGenerator

    team_ids = team_ids_provider()
    reporter = ReportGenerator()
    for tid in team_ids:
        try:
            reporter.generate_daily_report(tid)
        except Exception:
            logger.error("Daily report failed for team %s", tid, exc_info=True)


def _run_weekly_reports(team_ids_provider: Any) -> None:
    from app.dream.reporter import ReportGenerator

    team_ids = team_ids_provider()
    reporter = ReportGenerator()
    for tid in team_ids:
        try:
            reporter.generate_weekly_report(tid)
        except Exception:
            logger.error("Weekly report failed for team %s", tid, exc_info=True)


def _run_monthly_reports(team_ids_provider: Any) -> None:
    from app.dream.reporter import ReportGenerator

    team_ids = team_ids_provider()
    reporter = ReportGenerator()
    for tid in team_ids:
        try:
            reporter.generate_monthly_report(tid)
        except Exception:
            logger.error("Monthly report failed for team %s", tid, exc_info=True)


def _run_knowledge_extraction(team_ids_provider: Any) -> None:
    from app.dream.extractor import KnowledgeExtractor

    team_ids = team_ids_provider()
    extractor = KnowledgeExtractor()
    for tid in team_ids:
        try:
            extractor.extract_knowledge_candidates(tid)
        except Exception:
            logger.error("Knowledge extraction failed for team %s", tid, exc_info=True)


def _run_escalation_automation(team_ids_provider: Any) -> None:
    from app.engines.escalation import EscalationEngine, check_overdue_tasks

    team_ids = team_ids_provider()
    try:
        check_overdue_tasks(team_ids=team_ids)
    except Exception:
        logger.error("check_overdue_tasks failed", exc_info=True)

    engine = EscalationEngine()
    for tid in team_ids:
        try:
            candidates = engine.list_tasks_past_deadline(tid)
            for task in candidates:
                try:
                    engine.escalate(task["id"])
                except Exception:
                    logger.error(
                        "Escalation failed for task %s", task["id"], exc_info=True
                    )
        except Exception:
            logger.error("Escalation pass failed for team %s", tid, exc_info=True)


def _run_kpi_auto_score(team_ids_provider: Any) -> None:
    from app.engines.kpi import auto_score_system_kpis

    team_ids = team_ids_provider()
    try:
        auto_score_system_kpis(team_ids=team_ids)
    except Exception:
        logger.error("auto_score_system_kpis failed", exc_info=True)


def _run_anomaly_detection(team_ids_provider: Any) -> None:
    from app.engines.anomaly import detect_anomalies

    team_ids = team_ids_provider()
    try:
        detect_anomalies(team_ids=team_ids)
    except Exception:
        logger.error("detect_anomalies failed", exc_info=True)


def _run_retention_alerts(team_ids_provider: Any) -> None:
    from app.engines.customer import CustomerEngine

    team_ids = team_ids_provider()
    engine = CustomerEngine()
    for tid in team_ids:
        try:
            engine.check_churn_risk(tid)
        except Exception:
            logger.error("Retention alert failed for team %s", tid, exc_info=True)


def _run_approval_expiry() -> None:
    import asyncio
    try:
        from app.safety.approval import ApprovalGateway
        gateway = ApprovalGateway.get_instance()
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(gateway.expire_stale())
        except RuntimeError:
            asyncio.run(gateway.expire_stale())
    except Exception:
        logger.error("Approval expiry check failed", exc_info=True)


def _default_team_ids_provider() -> list[str]:
    try:
        from app.core.database import Database
        db = Database.get_instance()
        rows = db.query("teams", {"status": "active"}, limit=500)
        return [r["id"] for r in rows]
    except Exception:
        logger.error("Failed to fetch active team IDs", exc_info=True)
        return []
