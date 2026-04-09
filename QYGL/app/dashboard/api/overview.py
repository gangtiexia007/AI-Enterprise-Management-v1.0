"""P01: Overview page — stats, notifications, chat entry point."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.database import Database
from app.dashboard.app import templates, _global_context, render

router = APIRouter(tags=["overview"])


def _get_stats(db: Database) -> dict:
    today = datetime.utcnow().strftime("%Y-%m-%d")

    total_token_limit = 0
    total_token_used = 0
    models = db.query("models", {"enabled": True})
    for m in models:
        total_token_limit += m.get("daily_token_limit", 0) or 0
    usage_rows = db.execute(
        "SELECT SUM(total_tokens) as total FROM model_usage WHERE date=?", (today,)
    )
    total_token_used = (usage_rows[0]["total"] or 0) if usage_rows else 0
    token_pct = round(total_token_used / total_token_limit * 100, 1) if total_token_limit > 0 else 0

    return {
        "pending_approvals": db.count("approval_requests", {"status": "pending"}),
        "today_anomalies": (
            db.execute("SELECT COUNT(*) as cnt FROM escalations WHERE sent_at >= ?", (today,))[0]["cnt"]
        ),
        "active_teams": db.count("teams", {"status": "active"}) + db.count("teams", {"status": "live"}),
        "token_usage_pct": token_pct,
        "total_token_used": total_token_used,
        "total_token_limit": total_token_limit,
    }


def _get_notifications(db: Database, limit: int = 10) -> list[dict]:
    recent = db.query(
        "approval_requests",
        {"status": "pending"},
        order_by="created_at DESC",
        limit=limit,
    )
    notifications = []
    for r in recent:
        notifications.append({
            "id": r["id"],
            "type": "approval",
            "title": r.get("title", "待审批"),
            "time": r.get("created_at", ""),
            "url": f"/approvals/{r['id']}",
        })

    escalations = db.query("escalations", order_by="sent_at DESC", limit=5)
    for e in escalations:
        notifications.append({
            "id": e["id"],
            "type": "escalation",
            "title": f"升级处理: {e.get('message', '')[:30]}",
            "time": e.get("sent_at", ""),
            "url": f"/escalations/{e.get('task_id', '')}",
        })

    notifications.sort(key=lambda x: x.get("time", ""), reverse=True)
    return notifications[:limit]


def _compute_dashboard_metrics(db: Database) -> dict[str, object]:
    goals = db.query("goals", {"status": ["active", "tracking"]}, limit=50)
    company_goals = [g for g in goals if g.get("level") == "company"]
    total_target = sum(g.get("target_value", 0) or 0 for g in company_goals)
    total_current = sum(g.get("current_value", 0) or 0 for g in company_goals)
    goal_progress_pct = (
        round(total_current / total_target * 100, 1) if total_target > 0 else 0.0
    )

    total_tasks = db.count("tasks")
    completed_tasks = db.count("tasks", {"status": "completed"})
    scored_tasks = db.count("tasks", {"status": "scored"})
    completion_rate = (
        round((completed_tasks + scored_tasks) / total_tasks * 100, 1) if total_tasks > 0 else 0.0
    )

    now_iso = datetime.now().isoformat()
    overdue_rows = db.execute(
        """
        SELECT COUNT(*) as cnt FROM tasks
        WHERE deadline_at IS NOT NULL AND deadline_at != ''
          AND deadline_at < ?
          AND status NOT IN ('completed', 'scored', 'overdue')
        """,
        (now_iso,),
    )
    overdue_count = overdue_rows[0]["cnt"] if overdue_rows else 0

    kpi_rows = db.execute(
        "SELECT COUNT(*) as cnt FROM kpi_scores WHERE grade IN ('C', 'D')"
    )
    kpi_alerts_count = kpi_rows[0]["cnt"] if kpi_rows else 0

    teams = db.query("teams", order_by="display_name ASC, name ASC", limit=200)
    team_stats: list[dict[str, object]] = []
    for team in teams:
        tid = team["id"]
        t_tasks = db.count("tasks", {"team_id": tid})
        t_completed = db.count("tasks", {"team_id": tid, "status": ["completed", "scored"]})
        t_pending_approvals = db.count("approval_requests", {"team_id": tid, "status": "pending"})
        team_stats.append({
            "id": tid,
            "name": team.get("display_name") or team.get("name") or tid,
            "tasks_total": t_tasks,
            "tasks_completed": t_completed,
            "completion_rate": round(t_completed / t_tasks * 100) if t_tasks > 0 else 0,
            "pending_approvals": t_pending_approvals,
            "status": team.get("status", ""),
        })

    recent_activities = db.query("audit_logs", order_by="timestamp DESC", limit=10)

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_tokens = db.execute(
        "SELECT SUM(total_tokens) as total FROM model_usage WHERE date=?",
        (today_str,),
    )
    today_token_total = (today_tokens[0]["total"] or 0) if today_tokens else 0

    in_progress_tasks = db.count(
        "tasks",
        {"status": ["pending", "dispatched", "in_progress", "submitted"]},
    )

    pending_top = db.query(
        "approval_requests",
        {"status": "pending"},
        order_by="priority ASC, created_at DESC",
        limit=5,
    )

    overdue_tasks_rows = db.execute(
        """
        SELECT t.id, t.title, t.deadline_at, t.employee_id, e.name AS employee_name
        FROM tasks t
        LEFT JOIN employees e ON t.employee_id = e.id
        WHERE t.deadline_at IS NOT NULL AND t.deadline_at != ''
          AND t.deadline_at < ?
          AND t.status NOT IN ('completed', 'scored', 'overdue')
        ORDER BY t.deadline_at ASC
        LIMIT 10
        """,
        (now_iso,),
    )

    return {
        "goal_progress_pct": goal_progress_pct,
        "completion_rate": completion_rate,
        "overdue_count": overdue_count,
        "kpi_alerts_count": kpi_alerts_count,
        "team_stats": team_stats,
        "recent_activities": recent_activities,
        "today_token_total": today_token_total,
        "in_progress_tasks": in_progress_tasks,
        "pending_approvals_top5": pending_top,
        "overdue_tasks_list": overdue_tasks_rows,
    }


@router.get("/", response_class=HTMLResponse)
async def overview_page(request: Request):
    from fastapi.responses import RedirectResponse as _Redirect
    db = Database.get_instance()

    teams = db.query("teams", limit=1)
    if not teams:
        return _Redirect("/wizard/step1", status_code=302)

    ctx = _global_context(request)
    ctx["flash_msg"] = request.query_params.get("msg", "")

    ctx["stats"] = _get_stats(db)
    ctx["notifications"] = _get_notifications(db)

    metrics = _compute_dashboard_metrics(db)
    ctx.update(metrics)

    shadow_teams = db.query("team_shadow_config", {"mode": "shadow"})
    ctx["shadow_countdown"] = None
    for sc in shadow_teams:
        if sc.get("shadow_start_date"):
            try:
                start = datetime.fromisoformat(sc["shadow_start_date"])
                end = start + timedelta(days=sc.get("shadow_duration_days", 7))
                remaining = (end - datetime.utcnow()).days
                if remaining > 0:
                    ctx["shadow_countdown"] = {
                        "team_id": sc["team_id"],
                        "remaining_days": remaining,
                        "end_date": end.strftime("%Y-%m-%d"),
                    }
            except (ValueError, TypeError):
                pass

    team_stats = metrics.get("team_stats") or []
    ut = getattr(request.state, "user_teams", None)
    if ut:
        ctx["default_chat_team_id"] = ut[0]
    elif team_stats:
        ctx["default_chat_team_id"] = str(team_stats[0].get("id", ""))
    else:
        rows = db.query("teams", order_by="display_name ASC, name ASC", limit=1)
        ctx["default_chat_team_id"] = rows[0]["id"] if rows else ""

    return render(request, "pages/overview.html", ctx)
