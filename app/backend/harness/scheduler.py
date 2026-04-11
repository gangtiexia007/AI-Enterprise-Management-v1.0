"""
APScheduler-based scheduler for periodic business logic.

Jobs:
- periodic_checks: overdue detection + escalation + KPI calc (every N min)
- daily_report_push: morning report to boss via Feishu (daily 09:00)
- weekly_report_push: weekly summary (Monday 09:00)
- coaching_suggestions: AI coaching for underperformers (weekly)
- memory_distillation: extract knowledge from conversations (daily)
- token_budget_check: budget alerts (every 6 hours)
- approval_timeout_check: 48h/72h reminders (every 4 hours)
- kpi_alert_check: low KPI alerts (every 12 hours)
"""
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from database import SessionLocal
from models import Setting

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def _get_setting(key: str, default: str = "") -> str:
    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default
    except Exception:
        return default
    finally:
        db.close()


def _get_check_interval() -> int:
    return int(_get_setting("scheduler_interval_minutes", "30"))


def _run_periodic_checks():
    from harness.rules_engine import check_overdue_tasks, check_escalations, calculate_kpi_scores
    db = SessionLocal()
    try:
        overdue = check_overdue_tasks(db)
        escalations = check_escalations(db)
        kpi = calculate_kpi_scores(db)
        logger.info("Periodic: %d overdue, %d escalations, %d KPI recalc", overdue, escalations, kpi)
    except Exception:
        logger.exception("Error in periodic check")
    finally:
        db.close()


def _run_daily_report_push():
    """Generate daily report and push to boss via Feishu."""
    from harness.feishu_client import feishu_client
    db = SessionLocal()
    try:
        if not feishu_client.is_enabled():
            logger.info("Daily report: Feishu disabled, skipping push")
            return

        boss_id = _get_setting("feishu_boss_id")
        if not boss_id:
            logger.info("Daily report: no boss feishu_id configured")
            return

        from harness.rules_engine import _get_setting as rs_setting
        from models import Task, TaskStatus, Goal, KPIRecord, Employee
        from datetime import date
        from sqlalchemy import func

        today = date.today()
        total_tasks = db.query(Task).count()
        overdue = db.query(Task).filter(Task.deadline < today, Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])).count()
        done_today = db.query(Task).filter(Task.status == TaskStatus.DONE, func.date(Task.updated_at) == today).count()
        pending = db.query(Task).filter(Task.status == TaskStatus.PENDING).count()

        goals = db.query(Goal).filter(Goal.target_value > 0).all()
        goal_pct = 0
        if goals:
            goal_pct = round(sum(g.current_value / g.target_value for g in goals) / len(goals) * 100)

        report_lines = [
            f"**日期**: {today.isoformat()}",
            f"**任务总数**: {total_tasks}",
            f"**今日完成**: {done_today}",
            f"**待处理**: {pending}",
            f"**逾期**: {overdue}",
            f"**目标平均进度**: {goal_pct}%",
        ]

        if overdue > 0:
            overdue_tasks = db.query(Task).filter(Task.deadline < today, Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])).limit(5).all()
            report_lines.append("\n**逾期任务**:")
            for t in overdue_tasks:
                days = (today - t.deadline).days if t.deadline else 0
                report_lines.append(f"- {t.title} ({t.assignee_name or '未指派'}, 逾期{days}天)")

        report_text = "\n".join(report_lines)

        try:
            from harness.ai_client import ai_client
            import asyncio
            ai_prompt = f"请将以下管理数据转化为简洁的中文日报叙述（200字以内），重点突出问题和建议:\n\n{report_text}"
            loop = asyncio.new_event_loop()
            narrative = loop.run_until_complete(ai_client.chat(
                [{"role": "system", "content": "你是管理报告撰写助手，用简洁的中文叙述数据。"},
                 {"role": "user", "content": ai_prompt}],
                max_tokens=500,
            ))
            loop.close()
            if narrative and "失败" not in narrative:
                report_text = narrative
        except Exception as e:
            logger.debug(f"AI narrative failed, using raw data: {e}")

        feishu_client.send_daily_report(boss_id, report_text)
        _log_scheduled("daily_report", "Daily report pushed to Feishu")
    except Exception:
        logger.exception("Error in daily report push")
    finally:
        db.close()


def _run_weekly_report_push():
    """Generate weekly report and push to boss."""
    from harness.feishu_client import feishu_client
    db = SessionLocal()
    try:
        boss_id = _get_setting("feishu_boss_id")
        if not boss_id or not feishu_client.is_enabled():
            return

        from models import Task, TaskStatus, Goal
        from datetime import date, timedelta
        from sqlalchemy import func

        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        total_this_week = db.query(Task).filter(Task.created_at >= week_start.isoformat()).count()
        done_this_week = db.query(Task).filter(Task.status == TaskStatus.DONE, Task.updated_at >= week_start.isoformat()).count()
        overdue = db.query(Task).filter(Task.deadline < today, Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])).count()

        report = f"**本周报告** ({week_start} ~ {today})\n\n"
        report += f"- 新增任务: {total_this_week}\n- 完成任务: {done_this_week}\n- 当前逾期: {overdue}\n"

        feishu_client.send_weekly_report(boss_id, report)
        _log_scheduled("weekly_report", "Weekly report pushed")
    except Exception:
        logger.exception("Error in weekly report push")
    finally:
        db.close()


def _run_coaching_suggestions():
    """Identify underperformers and generate AI coaching suggestions."""
    db = SessionLocal()
    try:
        from models import KPIRecord, Employee, CoachingRecord
        from sqlalchemy import func

        threshold = float(_get_setting("kpi_alert_threshold", "60"))
        low_performers = (
            db.query(KPIRecord.employee_id, KPIRecord.employee_name, func.avg(KPIRecord.score).label("avg"))
            .group_by(KPIRecord.employee_id, KPIRecord.employee_name)
            .having(func.avg(KPIRecord.score) < threshold)
            .all()
        )

        for emp_id, emp_name, avg_score in low_performers:
            existing = db.query(CoachingRecord).filter(
                CoachingRecord.employee_id == emp_id,
                CoachingRecord.type == "ai_weekly",
            ).order_by(CoachingRecord.created_at.desc()).first()

            from datetime import timedelta
            if existing and (datetime.utcnow() - existing.created_at).days < 7:
                continue

            suggestion = f"员工 {emp_name} 的平均 KPI 得分为 {avg_score:.0f}，低于阈值 {threshold}。建议：1) 一对一沟通了解困难 2) 制定改进计划 3) 提供必要培训支持。"

            try:
                from harness.ai_client import ai_client
                import asyncio
                prompt = f"为绩效得分 {avg_score:.0f} 的员工 {emp_name} 生成简洁的改进建议（100字以内）"
                loop = asyncio.new_event_loop()
                ai_suggestion = loop.run_until_complete(ai_client.chat(
                    [{"role": "system", "content": "你是管理教练，给出具体可行的改进建议。"},
                     {"role": "user", "content": prompt}],
                    max_tokens=200,
                ))
                loop.close()
                if ai_suggestion and "失败" not in ai_suggestion:
                    suggestion = ai_suggestion
            except Exception:
                pass

            db.add(CoachingRecord(
                employee_id=emp_id,
                type="ai_weekly",
                content=f"KPI 均分 {avg_score:.0f}",
                ai_suggestion=suggestion,
            ))

        db.commit()
        _log_scheduled("coaching_suggestions", f"Checked {len(low_performers)} underperformers")
    except Exception:
        logger.exception("Error in coaching suggestions")
    finally:
        db.close()


def _run_memory_distillation():
    """Extract knowledge from recent conversations (L5→L4)."""
    try:
        from harness.memory_manager import memory_manager
        memory_manager.distill_conversations()
        _log_scheduled("memory_distillation", "Memory distillation completed")
    except Exception:
        logger.exception("Error in memory distillation")


def _run_token_budget_check():
    """Check token budget and send alerts."""
    try:
        from harness.token_budget import token_budget_manager
        alerts = token_budget_manager.check_budget_alerts()
        if alerts:
            _log_scheduled("token_budget_alert", f"{len(alerts)} alerts sent")
    except Exception:
        logger.exception("Error in token budget check")


def _run_approval_timeout_check():
    """Check for approval timeouts (48h/72h)."""
    from harness.rules_engine import check_approval_timeouts
    db = SessionLocal()
    try:
        acted = check_approval_timeouts(db)
        if acted:
            logger.info(f"Approval timeout check: {acted} actions")
    except Exception:
        logger.exception("Error in approval timeout check")
    finally:
        db.close()


def _run_kpi_alert_check():
    """Check for KPI scores below threshold."""
    from harness.rules_engine import check_kpi_alerts
    db = SessionLocal()
    try:
        alerted = check_kpi_alerts(db)
        if alerted:
            logger.info(f"KPI alert check: {alerted} alerts")
    except Exception:
        logger.exception("Error in KPI alert check")
    finally:
        db.close()


def _run_pod_rules():
    """Run POD data-driven rules (style grading, niche health, alerts)."""
    from harness.pod_rules import run_all_pod_rules
    db = SessionLocal()
    try:
        results = run_all_pod_rules(db)
        logger.info(f"POD rules: {results}")
    except Exception:
        logger.exception("Error in POD rules")
    finally:
        db.close()


def _run_currency_update():
    """每天早上 8:00 从 API 获取实时汇率"""
    import httpx
    import json
    db = SessionLocal()
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/cny.json"
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        cny_rates = data.get("cny", {})
        rates_to_cny = {
            "CNY": 1.0,
            "PHP": round(1 / cny_rates.get("php", 8.77), 6) if cny_rates.get("php") else 0.114,
            "MYR": round(1 / cny_rates.get("myr", 0.58), 6) if cny_rates.get("myr") else 1.722,
            "THB": round(1 / cny_rates.get("thb", 4.70), 6) if cny_rates.get("thb") else 0.213,
        }

        from datetime import date as d
        _upsert_setting(db, "currency_rates", json.dumps(rates_to_cny))
        _upsert_setting(db, "currency_rates_date", d.today().isoformat())
        _log_scheduled("currency_update", f"汇率已更新: {rates_to_cny}")
    except Exception as e:
        logger.warning(f"Currency update failed (using cached rates): {e}")
    finally:
        db.close()


def _upsert_setting(db, key: str, value: str):
    s = db.query(Setting).filter(Setting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def _run_product_order_refresh():
    """每天 11:00 刷新产品出单状态"""
    db = SessionLocal()
    try:
        from harness.pod_order_rules import run_hit_rate
        result = run_hit_rate(db)
        _log_scheduled("product_order_refresh", f"刷新了 {len(result)} 个运营的产品出单状态")
    except Exception:
        logger.exception("Error in product order refresh")
    finally:
        db.close()


def _run_weekly_kpi_aggregate():
    """每周二 10:00 聚合上周 KPI 并写入 KPIRecord"""
    db = SessionLocal()
    try:
        from datetime import date as d_cls, timedelta
        today = d_cls.today()
        week_end = today - timedelta(days=today.weekday())
        week_start = week_end - timedelta(days=7)
        period = f"{week_start.isocalendar()[0]}-W{week_start.isocalendar()[1]:02d}"

        from harness.pod_order_rules import sync_kpi_records
        count = sync_kpi_records(db, period)
        _log_scheduled("weekly_kpi_aggregate", f"已同步 {count} 条 KPI 记录 (period={period})")
    except Exception:
        logger.exception("Error in weekly KPI aggregate")
    finally:
        db.close()


def _log_scheduled(task_type: str, detail: str):
    from models import AuditLog
    db = SessionLocal()
    try:
        db.add(AuditLog(action=f"scheduled:{task_type}", detail=detail, actor="scheduler", resource_type="scheduled_task"))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


def _parse_time(time_str: str) -> tuple[int, int]:
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        return 9, 0


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    interval = _get_check_interval()
    report_time = _get_setting("report_time", "09:00")
    hour, minute = _parse_time(report_time)

    _scheduler = BackgroundScheduler()

    _scheduler.add_job(_run_periodic_checks, IntervalTrigger(minutes=interval), id="periodic_checks")
    _scheduler.add_job(_run_daily_report_push, CronTrigger(hour=hour, minute=minute), id="daily_report_push")
    _scheduler.add_job(_run_weekly_report_push, CronTrigger(day_of_week="mon", hour=hour, minute=minute + 30), id="weekly_report_push")
    _scheduler.add_job(_run_coaching_suggestions, CronTrigger(day_of_week="fri", hour=18), id="coaching_suggestions")
    _scheduler.add_job(_run_memory_distillation, CronTrigger(hour=2), id="memory_distillation")
    _scheduler.add_job(_run_token_budget_check, IntervalTrigger(hours=6), id="token_budget_check")
    _scheduler.add_job(_run_approval_timeout_check, IntervalTrigger(hours=4), id="approval_timeout_check")
    _scheduler.add_job(_run_kpi_alert_check, IntervalTrigger(hours=12), id="kpi_alert_check")
    _scheduler.add_job(_run_pod_rules, CronTrigger(hour=10), id="pod_rules_daily")
    _scheduler.add_job(_run_currency_update, CronTrigger(hour=0, minute=30), id="currency_update")
    _scheduler.add_job(_run_product_order_refresh, CronTrigger(hour=11), id="product_order_refresh")
    _scheduler.add_job(_run_weekly_kpi_aggregate, CronTrigger(day_of_week="tue", hour=10), id="weekly_kpi_aggregate")

    _scheduler.start()
    logger.info(
        "Scheduler started — checks every %dm, daily report at %02d:%02d",
        interval, hour, minute,
    )


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


TASK_TYPE_TO_JOB_ID: dict[str, str] = {
    "daily_report": "daily_report_push",
    "weekly_report": "weekly_report_push",
    "coaching": "coaching_suggestions",
    "memory_distill": "memory_distillation",
    "token_budget": "token_budget_check",
    "approval_timeout": "approval_timeout_check",
    "kpi_alert": "kpi_alert_check",
    "pod_rules": "pod_rules_daily",
    "currency_update": "currency_update",
    "product_refresh": "product_order_refresh",
    "kpi_aggregate": "weekly_kpi_aggregate",
}
