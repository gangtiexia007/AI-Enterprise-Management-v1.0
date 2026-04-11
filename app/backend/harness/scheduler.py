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


def _run_weekly_three_questions():
    """每周一 09:30 为每个运营自动创建三问周报任务，并推送飞书通知。
    
    三问：
    1. 上周上了多少链接？哪条表现最好？
    2. 本周打算主攻哪个赛道/方向？
    3. 有没有遇到什么问题需要支持？
    """
    from harness.feishu_client import feishu_client
    db = SessionLocal()
    try:
        from models import Employee, Task, TaskStatus
        from datetime import date, timedelta

        today = date.today()
        next_friday = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
        
        iso = today.isocalendar()
        week_label = f"{iso[0]}-W{iso[1]:02d}"

        operators = db.query(Employee).filter(
            Employee.department == "POD运营",
            Employee.name != "",
        ).all()

        created = 0
        for emp in operators:
            existing = db.query(Task).filter(
                Task.assignee_name == emp.name,
                Task.task_type == "pod_weekly_standup",
                Task.created_at >= today.isoformat(),
            ).first()
            if existing:
                continue

            task = Task(
                title=f"[{week_label}] 三问周报 — {emp.name}",
                description=(
                    f"**本周三问（{week_label}）**\n\n"
                    "1️⃣ 上周上了多少链接？哪条产品表现最好（出单最多）？\n"
                    "2️⃣ 本周打算主攻哪个赛道/产品方向？\n"
                    "3️⃣ 有没有遇到什么问题或需要支持的地方？\n\n"
                    "请在本周五前回复完成。"
                ),
                assignee_id=emp.id,
                assignee_name=emp.name,
                deadline=next_friday,
                status=TaskStatus.DISPATCHED,
                task_type="pod_weekly_standup",
                priority="normal",
            )
            db.add(task)
            db.flush()

            if emp.feishu_id:
                feishu_client.send_task_notification(
                    emp.feishu_id,
                    task.title,
                    task.description,
                    str(next_friday),
                    emp.name,
                )
            created += 1

        db.commit()
        _log_scheduled("weekly_three_questions", f"创建了 {created} 个三问周报任务 ({week_label})")
    except Exception:
        logger.exception("Error in weekly three questions")
    finally:
        db.close()


def _run_weekly_kpi_ranking_report():
    """每周二 10:30 生成上周 KPI 排名并推送飞书给老板/主管。"""
    from harness.feishu_client import feishu_client
    db = SessionLocal()
    try:
        boss_id = _get_setting("feishu_boss_id")
        supervisor_id = _get_setting("feishu_supervisor_id", "")
        if not feishu_client.is_enabled():
            logger.info("Weekly KPI ranking: Feishu disabled, skipping push")
            return
        if not boss_id:
            logger.info("Weekly KPI ranking: no boss feishu_id configured")
            return

        from harness.pod_order_rules import run_operator_kpi, run_hit_rate
        from datetime import date, timedelta

        today = date.today()
        week_end = today - timedelta(days=today.weekday())
        week_start = week_end - timedelta(days=7)
        period_label = f"{week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')}"

        kpi_list = run_operator_kpi(db, period_start=week_start, period_end=week_end)
        hit_list = run_hit_rate(db)
        hit_map = {h["operator"]: h["hit_rate"] for h in hit_list}

        kpi_list.sort(key=lambda x: x["total_orders"], reverse=True)

        lines = [f"**运营周报排名** ({period_label})\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(kpi_list[:10]):
            medal = medals[i] if i < 3 else f"{i+1}."
            hit_rate = hit_map.get(r["operator"], 0)
            lines.append(
                f"{medal} **{r['operator']}**  "
                f"出单 {r['total_orders']} | GMV ¥{r['total_gmv_cny']:,.0f} | "
                f"有效链接 {r['valid_links']} | S爆款 {r['s_level_count']} | "
                f"命中率 {hit_rate}% | 取消率 {r['cancel_rate']}%"
            )

        if len(kpi_list) == 0:
            lines.append("本周暂无出单数据，请确认是否已导入 ERP 订单。")

        report_text = "\n".join(lines)
        card = feishu_client.build_report_card("本周运营 KPI 排名", report_text, str(today))
        feishu_client.send_card_message(boss_id, card)
        if supervisor_id:
            feishu_client.send_card_message(supervisor_id, card)

        _log_scheduled("weekly_kpi_ranking", f"已推送 {len(kpi_list)} 个运营的周排名")
    except Exception:
        logger.exception("Error in weekly KPI ranking report")
    finally:
        db.close()


def _run_monthly_goals_update():
    """每月 1 号 08:00 为每个运营创建/更新月度 Goal。"""
    db = SessionLocal()
    try:
        from harness.pod_order_rules import sync_monthly_goals
        from datetime import date

        today = date.today()
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1

        count = sync_monthly_goals(db, year=year, month=month)
        _log_scheduled("monthly_goals_update", f"已同步 {count} 个月度目标 ({year}-{month:02d})")
    except Exception:
        logger.exception("Error in monthly goals update")
    finally:
        db.close()


def _run_monthly_review_push():
    """每月 1 号 09:00 生成复盘报告并推飞书。"""
    from harness.feishu_client import feishu_client
    db = SessionLocal()
    try:
        boss_id = _get_setting("feishu_boss_id")
        if not feishu_client.is_enabled() or not boss_id:
            logger.info("Monthly review: Feishu disabled or boss_id not set")
            return

        from harness.pod_order_rules import run_monthly_review
        review = run_monthly_review(db)

        lines = [f"**{review['period']} 月度复盘报告**\n", f"对比上月：{review['prev_period']}\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(review["operators"][:10]):
            medal = medals[i] if i < 3 else f"{i+1}."
            growth = row["order_growth"]
            growth_str = f"↑{growth}%" if growth > 0 else (f"↓{abs(growth)}%" if growth < 0 else "持平")
            lines.append(
                f"{medal} **{row['operator']}** "
                f"出单 {row['this_month']['total_orders']} ({growth_str}) | "
                f"GMV ¥{row['this_month']['total_gmv_cny']:,.0f} | "
                f"S爆款 {row['this_month']['s_level_count']}"
            )

        if review.get("top_operator"):
            lines.append(f"\n🏆 月度第一：**{review['top_operator']}**，恭喜！")
        if review.get("bottom_operator") and review["total_operators"] > 1:
            lines.append(f"⚠️ 本月垫底：**{review['bottom_operator']}**，请关注。")

        report_text = "\n".join(lines)
        card = feishu_client.build_report_card("月度运营复盘", report_text, review["period"])
        feishu_client.send_card_message(boss_id, card)
        _log_scheduled("monthly_review_push", f"月度复盘已推送 ({review['period']})")
    except Exception:
        logger.exception("Error in monthly review push")
    finally:
        db.close()


def _run_elimination_alert_check():
    """每月 2 号检查连续垫底/三问未提交/月度第一，执行预警和奖励通知。"""
    from harness.feishu_client import feishu_client
    db = SessionLocal()
    try:
        from harness.pod_order_rules import check_elimination_and_rewards
        from models import Task, TaskStatus, Employee

        alerts = check_elimination_and_rewards(db)
        boss_id = _get_setting("feishu_boss_id")

        for alert in alerts.get("bottom_alerts", []):
            msg = (
                f"⚠️ 绩效预警\n\n"
                f"运营 **{alert['operator']}** 已连续 {alert['consecutive_months']} 个月出单排名垫底。\n"
                f"涉及周期：{' / '.join(alert.get('periods', []))}\n\n"
                f"建议：一对一沟通 + 制定改进计划，或启动人员调整流程。"
            )
            if boss_id and feishu_client.is_enabled():
                feishu_client.send_text_message(boss_id, msg)
            _log_scheduled("elimination_alert", f"{alert['operator']} 连续垫底预警")

        for missing in alerts.get("standup_missing", []):
            op_msg = (
                f"📋 三问周报提醒\n\n"
                f"你已连续 {missing['missing_weeks']} 周未提交三问周报。\n"
                f"请尽快补交，否则将影响本月绩效评分。"
            )
            feishu_id = missing.get("feishu_id")
            if feishu_id and feishu_client.is_enabled():
                feishu_client.send_text_message(feishu_id, op_msg)
            if boss_id and feishu_client.is_enabled():
                boss_msg = f"⚠️ {missing['operator']} 已连续 {missing['missing_weeks']} 周未提交三问周报"
                feishu_client.send_text_message(boss_id, boss_msg)
            _log_scheduled("standup_missing_alert", f"{missing['operator']} 连续未提交三问")

        top = alerts.get("top_reward")
        if top and boss_id and feishu_client.is_enabled():
            msg = (
                f"🏆 月度第一通知\n\n"
                f"恭喜 **{top['operator']}** 荣获 {top['period']} 月度运营第一！\n"
                f"出单量：{top['total_orders']} 单 | GMV：¥{top['total_gmv_cny']:,.0f}\n\n"
                f"建议：公开表扬 + 经验分享，激励团队。"
            )
            feishu_client.send_text_message(boss_id, msg)
            _log_scheduled("top_reward_notify", f"{top['operator']} 月度第一通知")

    except Exception:
        logger.exception("Error in elimination alert check")
    finally:
        db.close()


def _run_ai_niche_batch():
    """每天 03:00 批量 AI 补分类未命中的赛道。"""
    db = SessionLocal()
    try:
        from harness.pod_order_rules import run_ai_niche_classification
        count = run_ai_niche_classification(db, batch_size=100)
        _log_scheduled("ai_niche_batch", f"AI 赛道补分类: {count} 条")
    except Exception:
        logger.exception("Error in AI niche batch")
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
    _scheduler.add_job(_run_weekly_three_questions, CronTrigger(day_of_week="mon", hour=9, minute=30), id="weekly_three_questions")
    _scheduler.add_job(_run_weekly_kpi_ranking_report, CronTrigger(day_of_week="tue", hour=10, minute=30), id="weekly_kpi_ranking_report")
    _scheduler.add_job(_run_monthly_goals_update, CronTrigger(day=1, hour=8), id="monthly_goals_update")
    _scheduler.add_job(_run_monthly_review_push, CronTrigger(day=1, hour=9), id="monthly_review_push")
    _scheduler.add_job(_run_elimination_alert_check, CronTrigger(day=2, hour=9), id="elimination_alert_check")
    _scheduler.add_job(_run_ai_niche_batch, CronTrigger(hour=3), id="ai_niche_batch")

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
    "weekly_three_questions": "weekly_three_questions",
    "weekly_kpi_ranking": "weekly_kpi_ranking_report",
    "monthly_goals": "monthly_goals_update",
    "monthly_review": "monthly_review_push",
    "elimination_alert": "elimination_alert_check",
    "ai_niche": "ai_niche_batch",
}
