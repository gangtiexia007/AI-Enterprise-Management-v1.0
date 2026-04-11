"""
POD-specific business rules driven by Bitable data.

Runs on a schedule — reads 款式跟踪表 + 赛道管理表 from Bitable,
applies grading / health scoring, writes results back, and creates
system Tasks when thresholds are met.
"""
import json
import logging
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session

from models import Task, TaskStatus, Employee, Setting, AuditLog

logger = logging.getLogger(__name__)


def _get_setting(db: Session, key: str, default: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default


def _bitable_cfg(db: Session):
    token = _get_setting(db, "bitable_base_token")
    raw = _get_setting(db, "bitable_table_map", "{}")
    try:
        table_map = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        table_map = {}
    return token, table_map


def _numeric(fields: dict, key: str):
    v = fields.get(key)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list) and v:
        v = v[0].get("text") if isinstance(v[0], dict) else v[0]
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _text(fields: dict, key: str) -> str:
    v = fields.get(key)
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts = []
        for x in v:
            if isinstance(x, dict):
                parts.append(x.get("text") or x.get("name") or "")
            else:
                parts.append(str(x))
        return " ".join(parts)
    return str(v)


def _date_val(fields: dict, key: str):
    v = fields.get(key)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = v / 1000 if v > 1e12 else v
        return datetime.fromtimestamp(ts).date()
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(v.strip()[:10], fmt).date()
            except ValueError:
                continue
    return None


def _find_employee_by_dept(db: Session, department: str):
    return db.query(Employee).filter(Employee.department == department).first()


def _create_task_if_not_exists(
    db: Session,
    title: str,
    description: str,
    task_type: str,
    department: str,
    deadline_days: int = 2,
    priority: str = "high",
):
    """Create a task only if one with the same title doesn't already exist (pending/dispatched)."""
    existing = (
        db.query(Task)
        .filter(
            Task.title == title,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.DISPATCHED, TaskStatus.IN_PROGRESS]),
        )
        .first()
    )
    if existing:
        return None

    assignee = _find_employee_by_dept(db, department)
    task = Task(
        title=title,
        description=description,
        task_type=task_type,
        assignee_id=assignee.id if assignee else None,
        assignee_name=assignee.name if assignee else "",
        deadline=date.today() + timedelta(days=deadline_days),
        priority=priority,
        status=TaskStatus.DISPATCHED,
    )
    db.add(task)
    return task


# ──── Rule 1: Auto-grade styles after 7 days ────

GRADE_RULES = {
    "S": {"min_orders_7d": 5, "min_favorites_7d": 10},
    "A": {"min_orders_7d": 2, "min_favorites_7d": 5},
    "B": {"min_orders_7d": 1, "min_favorites_7d": 0},
}


def _grade_style(fields: dict) -> str:
    orders = _numeric(fields, "7日出单量") or 0
    favs = _numeric(fields, "7日收藏量") or 0
    click_rate = _numeric(fields, "3日点击率") or 0

    if orders >= 5 or (orders >= 3 and favs >= 10):
        return "S"
    if orders >= 2 or (orders >= 1 and favs >= 5) or click_rate >= 5:
        return "A"
    if orders >= 1 or favs >= 3 or click_rate >= 2:
        return "B"
    return "C"


def run_style_grading(db: Session) -> int:
    """Grade styles in 款式跟踪表 that have been live for ≥7 days."""
    from harness.bitable_client import bitable_client

    token, table_map = _bitable_cfg(db)
    tid = (table_map.get("款式跟踪表") or "").strip()
    if not token or not tid:
        logger.info("Style grading: 款式跟踪表 not configured, skipping")
        return 0

    today = date.today()
    items = bitable_client.list_all_record_ids(token, tid, max_pages=20)
    graded = 0

    for rec in items:
        fields = rec.get("fields") or {}
        record_id = rec.get("record_id")
        if not record_id:
            continue

        upload_date = _date_val(fields, "上架日期")
        if not upload_date:
            continue

        current_grade = _text(fields, "款式分级").strip()
        days_since = (today - upload_date).days

        if days_since >= 7 and not current_grade:
            new_grade = _grade_style(fields)
            try:
                bitable_client.update_record(token, tid, record_id, {"款式分级": new_grade})
                graded += 1
                logger.info(f"Graded style {_text(fields, '编号')} → {new_grade}")
            except Exception as e:
                logger.warning(f"Failed to grade {record_id}: {e}")

            if new_grade == "S":
                niche = _text(fields, "所属赛道") or "未知赛道"
                code = _text(fields, "编号") or record_id
                _create_task_if_not_exists(
                    db,
                    title=f"变体制作：{code} ({niche})",
                    description=f"S 级爆款 {code} 需制作 5-10 个变体（换文案/配色/字体/排版），移入垂直店。",
                    task_type="变体制作",
                    department="铺货组",
                    deadline_days=2,
                )

    if graded:
        db.commit()
    return graded


# ──── Rule 2: 3-day data check reminder ────

def run_data_entry_reminders(db: Session) -> int:
    """For styles uploaded 3 days ago with no click data, create reminder tasks."""
    from harness.bitable_client import bitable_client

    token, table_map = _bitable_cfg(db)
    tid = (table_map.get("款式跟踪表") or "").strip()
    if not token or not tid:
        return 0

    today = date.today()
    target_date = today - timedelta(days=3)
    items = bitable_client.list_all_record_ids(token, tid, max_pages=20)
    created = 0

    for rec in items:
        fields = rec.get("fields") or {}
        upload_date = _date_val(fields, "上架日期")
        if not upload_date or upload_date != target_date:
            continue

        click_rate = _numeric(fields, "3日点击率")
        if click_rate is not None and click_rate > 0:
            continue

        code = _text(fields, "编号") or rec.get("record_id", "")
        niche = _text(fields, "所属赛道") or ""
        task = _create_task_if_not_exists(
            db,
            title=f"数据录入：{code} 3日数据",
            description=f"款式 {code}（{niche}）上架已满 3 天，请在款式跟踪表中录入曝光/点击数据。",
            task_type="数据检查",
            department="优化组",
            deadline_days=1,
        )
        if task:
            created += 1

    if created:
        db.commit()
    return created


# ──── Rule 3: Niche health scoring ────

def run_niche_health(db: Session) -> int:
    """Compute health for each niche in 赛道管理表 based on S+A ratio."""
    from harness.bitable_client import bitable_client

    token, table_map = _bitable_cfg(db)
    niche_tid = (table_map.get("赛道管理表") or "").strip()
    style_tid = (table_map.get("款式跟踪表") or "").strip()
    if not token or not niche_tid:
        logger.info("Niche health: 赛道管理表 not configured, skipping")
        return 0

    niche_items = bitable_client.list_all_record_ids(token, niche_tid, max_pages=10)
    style_items = []
    if style_tid:
        style_items = bitable_client.list_all_record_ids(token, style_tid, max_pages=20)

    niche_grades: dict[str, dict[str, int]] = {}
    for rec in style_items:
        fields = rec.get("fields") or {}
        niche_name = _text(fields, "所属赛道").strip()
        grade = _text(fields, "款式分级").strip().upper()
        if niche_name and grade in ("S", "A", "B", "C"):
            if niche_name not in niche_grades:
                niche_grades[niche_name] = {"S": 0, "A": 0, "B": 0, "C": 0, "total": 0}
            niche_grades[niche_name][grade] += 1
            niche_grades[niche_name]["total"] += 1

    updated = 0
    for rec in niche_items:
        fields = rec.get("fields") or {}
        record_id = rec.get("record_id")
        niche_name = _text(fields, "赛道名称").strip()
        if not record_id or not niche_name:
            continue

        stats = niche_grades.get(niche_name, {"S": 0, "A": 0, "B": 0, "C": 0, "total": 0})
        total = stats["total"]
        s_count = stats["S"]
        a_count = stats["A"]

        sa_ratio = (s_count + a_count) / total if total > 0 else 0
        health = "健康" if sa_ratio >= 0.3 else ("警告" if sa_ratio >= 0.1 else "放弃")

        update_fields = {
            "S级款数": s_count,
            "A级款数": a_count,
            "健康度": health,
        }

        try:
            bitable_client.update_record(token, niche_tid, record_id, update_fields)
            updated += 1
        except Exception as e:
            logger.warning(f"Failed to update niche health for {niche_name}: {e}")

    return updated


# ──── Rule 4: No-exposure alert ────

def run_no_exposure_alerts(db: Session) -> int:
    """Styles live ≥3 days with zero exposure → create optimization task."""
    from harness.bitable_client import bitable_client

    token, table_map = _bitable_cfg(db)
    tid = (table_map.get("款式跟踪表") or "").strip()
    if not token or not tid:
        return 0

    today = date.today()
    items = bitable_client.list_all_record_ids(token, tid, max_pages=20)
    created = 0

    for rec in items:
        fields = rec.get("fields") or {}
        upload_date = _date_val(fields, "上架日期")
        if not upload_date or (today - upload_date).days < 3:
            continue

        exposure = _numeric(fields, "3日曝光量") or 0
        if exposure > 0:
            continue

        current_status = _text(fields, "当前状态").strip()
        if current_status in ("已淘汰", "已优化"):
            continue

        code = _text(fields, "编号") or rec.get("record_id", "")
        niche = _text(fields, "所属赛道") or ""
        task = _create_task_if_not_exists(
            db,
            title=f"优化标题标签：{code}",
            description=f"款式 {code}（{niche}）上架超过 3 天零曝光，请优化标题、标签和主图。",
            task_type="产品优化",
            department="优化组",
            deadline_days=2,
        )
        if task:
            created += 1

    if created:
        db.commit()
    return created


# ──── Combined entry point (called by scheduler) ────

def run_all_pod_rules(db: Session) -> dict:
    """Run all POD rules and return summary."""
    results = {}
    try:
        results["styles_graded"] = run_style_grading(db)
    except Exception as e:
        logger.exception("Style grading failed")
        results["styles_graded_error"] = str(e)

    try:
        results["data_reminders"] = run_data_entry_reminders(db)
    except Exception as e:
        logger.exception("Data entry reminders failed")
        results["data_reminders_error"] = str(e)

    try:
        results["niches_updated"] = run_niche_health(db)
    except Exception as e:
        logger.exception("Niche health failed")
        results["niches_updated_error"] = str(e)

    try:
        results["exposure_alerts"] = run_no_exposure_alerts(db)
    except Exception as e:
        logger.exception("No-exposure alerts failed")
        results["exposure_alerts_error"] = str(e)

    db.add(AuditLog(
        action="pod_rules_run",
        detail=json.dumps(results, ensure_ascii=False),
        actor="scheduler",
        resource_type="pod",
    ))
    db.commit()

    logger.info(f"POD rules completed: {results}")
    return results
