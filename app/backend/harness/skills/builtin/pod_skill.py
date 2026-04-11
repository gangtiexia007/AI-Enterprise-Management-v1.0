"""POD-specific Agent skills — niche status, style grading report, weekly report, create niche chain."""
from __future__ import annotations

import json
from datetime import date, timedelta

from harness.skill_registry import tool, ToolResult


def _session_db(db_session):
    if db_session is not None:
        return db_session, False
    from database import SessionLocal
    return SessionLocal(), True


def _bitable_settings(db):
    from models import Setting

    def gs(key, default=""):
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default

    token = gs("bitable_base_token")
    raw = gs("bitable_table_map", "{}")
    try:
        m = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        m = {}
    return token, m


def _text(fields: dict, key: str) -> str:
    v = fields.get(key)
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(
            (x.get("text") or x.get("name") or str(x)) if isinstance(x, dict) else str(x)
            for x in v
        )
    return str(v)


def _num(fields: dict, key: str):
    v = fields.get(key)
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0


@tool(
    name="niche_status",
    description="查询指定赛道的当前状态（阶段、款式数、出单量、健康度等）。用法：'XX 赛道什么情况？'",
    parameters={
        "type": "object",
        "properties": {
            "niche_name": {"type": "string", "description": "赛道名称关键词"},
        },
        "required": ["niche_name"],
    },
    permission_level=0,
)
async def niche_status(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        tid = (table_map.get("赛道管理表") or "").strip()
        if not token or not tid:
            return ToolResult(success=False, error="赛道管理表未配置。")

        keyword = (kwargs.get("niche_name") or "").strip().lower()
        items = bitable_client.list_all_record_ids(token, tid, max_pages=5)
        matches = []
        for rec in items:
            fields = rec.get("fields") or {}
            name = _text(fields, "赛道名称")
            if keyword and keyword not in name.lower():
                continue
            matches.append({
                "赛道名称": name,
                "业务线": _text(fields, "业务线"),
                "阶段": _text(fields, "阶段"),
                "首批款式数": _num(fields, "首批款式数"),
                "S级款数": _num(fields, "S级款数"),
                "A级款数": _num(fields, "A级款数"),
                "7日总出单": _num(fields, "7日总出单"),
                "健康度": _text(fields, "健康度"),
                "下一步动作": _text(fields, "下一步动作"),
            })

        if not matches:
            return ToolResult(success=True, data={"message": f"未找到匹配「{keyword}」的赛道"})
        return ToolResult(success=True, data={"niches": matches, "count": len(matches)})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


@tool(
    name="style_grading_report",
    description="查看需要做分级判断的款式（上架满 7 天但尚未分级的款式列表）。",
    parameters={
        "type": "object",
        "properties": {
            "days_threshold": {"type": "integer", "description": "上架天数阈值，默认 7"},
        },
        "required": [],
    },
    permission_level=0,
)
async def style_grading_report(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        tid = (table_map.get("款式跟踪表") or "").strip()
        if not token or not tid:
            return ToolResult(success=False, error="款式跟踪表未配置。")

        days = int(kwargs.get("days_threshold") or 7)
        today = date.today()
        cutoff = today - timedelta(days=days)

        items = bitable_client.list_all_record_ids(token, tid, max_pages=20)
        pending = []
        for rec in items:
            fields = rec.get("fields") or {}
            grade = _text(fields, "款式分级").strip()
            if grade:
                continue
            upload_raw = fields.get("上架日期")
            if upload_raw is None:
                continue
            from harness.pod_rules import _date_val
            upload = _date_val(fields, "上架日期")
            if upload and upload <= cutoff:
                pending.append({
                    "编号": _text(fields, "编号"),
                    "所属赛道": _text(fields, "所属赛道"),
                    "平台": _text(fields, "平台"),
                    "上架日期": str(upload),
                    "3日曝光量": _num(fields, "3日曝光量"),
                    "3日点击率": _num(fields, "3日点击率"),
                    "7日出单量": _num(fields, "7日出单量"),
                    "7日收藏量": _num(fields, "7日收藏量"),
                })

        return ToolResult(success=True, data={
            "pending_grading_count": len(pending),
            "styles": pending[:50],
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


@tool(
    name="pod_weekly_report",
    description="生成本周各赛道排名报告：按 7 日出单量排序，显示各赛道的款式数和健康度。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    permission_level=0,
)
async def pod_weekly_report(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        niche_tid = (table_map.get("赛道管理表") or "").strip()
        style_tid = (table_map.get("款式跟踪表") or "").strip()
        if not token or not niche_tid:
            return ToolResult(success=False, error="赛道管理表未配置。")

        niches = bitable_client.list_all_record_ids(token, niche_tid, max_pages=10)
        ranking = []
        for rec in niches:
            fields = rec.get("fields") or {}
            name = _text(fields, "赛道名称")
            stage = _text(fields, "阶段")
            if stage in ("已归档",):
                continue
            ranking.append({
                "赛道名称": name,
                "阶段": stage,
                "S级": _num(fields, "S级款数"),
                "A级": _num(fields, "A级款数"),
                "7日总出单": _num(fields, "7日总出单"),
                "健康度": _text(fields, "健康度"),
            })
        ranking.sort(key=lambda x: x["7日总出单"], reverse=True)

        style_stats = {"total": 0, "S": 0, "A": 0, "B": 0, "C": 0, "ungraded": 0}
        if style_tid:
            styles = bitable_client.list_all_record_ids(token, style_tid, max_pages=20)
            for rec in styles:
                fields = rec.get("fields") or {}
                grade = _text(fields, "款式分级").strip().upper()
                style_stats["total"] += 1
                if grade in ("S", "A", "B", "C"):
                    style_stats[grade] += 1
                else:
                    style_stats["ungraded"] += 1

        return ToolResult(success=True, data={
            "niche_ranking": ranking,
            "style_summary": style_stats,
            "report_date": str(date.today()),
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


@tool(
    name="create_niche_task_chain",
    description="开启新赛道测试：在赛道管理表创建记录 + 自动创建 研究→铺货→检查 的任务链。用法：'测试 XX 赛道'",
    parameters={
        "type": "object",
        "properties": {
            "niche_name": {"type": "string", "description": "三级细分赛道名称，如 'Shih Tzu Mom PH'"},
            "business_line": {"type": "string", "description": "业务线，如 '菲律宾线' / '欧美线'"},
            "researcher": {"type": "string", "description": "研究员姓名（可选）"},
        },
        "required": ["niche_name"],
    },
    permission_level=2,
)
async def create_niche_task_chain(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client
    from models import Task, TaskStatus, Employee, AuditLog
    from schemas import TASK_TEMPLATES

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        niche_tid = (table_map.get("赛道管理表") or "").strip()
        if not token or not niche_tid:
            return ToolResult(success=False, error="赛道管理表未配置。")

        name = kwargs.get("niche_name") or ""
        biz_line = kwargs.get("business_line") or ""
        researcher = kwargs.get("researcher") or ""

        niche_fields = {
            "赛道名称": name,
            "阶段": "待测试",
            "测试开始日": int(date.today().strftime("%s")) * 1000,
        }
        if biz_line:
            niche_fields["业务线"] = biz_line
        if researcher:
            niche_fields["研究员"] = researcher

        try:
            niche_rec = bitable_client.create_record(token, niche_tid, niche_fields)
        except Exception as e:
            return ToolResult(success=False, error=f"创建赛道记录失败: {e}")

        research_assignee = db.query(Employee).filter(Employee.department == "研究组").first()
        tpl = TASK_TEMPLATES.get("赛道研究", {})

        research_task = Task(
            title=f"赛道研究：{name}",
            description=f"研究并验证 {name} 赛道的市场潜力，输出文案方向和设计风格清单。",
            task_type="赛道研究",
            assignee_id=research_assignee.id if research_assignee else None,
            assignee_name=research_assignee.name if research_assignee else "",
            deadline=date.today() + timedelta(days=3),
            priority="high",
            auto_next_config=tpl.get("auto_next_config", ""),
            status=TaskStatus.DISPATCHED,
        )
        db.add(research_task)
        db.commit()
        db.refresh(research_task)

        if research_assignee and research_assignee.feishu_id:
            try:
                from harness.feishu_client import feishu_client
                feishu_client.send_task_notification(
                    research_assignee.feishu_id,
                    research_task.title,
                    description=research_task.description,
                    deadline=str(research_task.deadline),
                    assignee=research_assignee.name,
                )
            except Exception:
                pass

        db.add(AuditLog(
            action="niche_created",
            detail=f"新赛道「{name}」已创建，首个任务已派发给研究组",
            actor="agent",
            resource_type="niche",
            resource_id=name,
        ))
        db.commit()

        return ToolResult(success=True, data={
            "niche_name": name,
            "niche_record": niche_rec,
            "task_id": research_task.id,
            "task_title": research_task.title,
            "assignee": research_task.assignee_name or "未指派",
            "chain": "赛道研究 → 铺货上架 → 数据检查（完成后自动触发下一步）",
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()
