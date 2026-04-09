from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, date
from database import get_db
from models import Conversation, Task, TaskStatus, Goal, KPIRecord, Employee, AuditLog, Setting
from schemas import MessageIn, ConversationOut

router = APIRouter()

def _get_setting_value(db: Session, key: str, default: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default

def _log_audit(db: Session, action: str, detail: str = ""):
    db.add(AuditLog(action=action, detail=detail, actor="agent", resource_type="conversation"))
    db.commit()

def _today_tasks(db: Session) -> str:
    tasks = db.query(Task).filter(Task.deadline == date.today()).all()
    if not tasks:
        return "今日无待办任务。"
    lines = [f"📋 今日待办 ({len(tasks)} 项):"]
    for t in tasks:
        s = t.status.value if hasattr(t.status, 'value') else t.status
        lines.append(f"  • {t.title} [{s}] - {t.assignee_name or '未指派'}")
    return "\n".join(lines)

def _overdue_tasks(db: Session) -> str:
    tasks = db.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).all()
    if not tasks:
        return "当前无逾期任务。"
    lines = [f"⚠️ 逾期任务 ({len(tasks)} 项):"]
    for t in tasks:
        lines.append(f"  • {t.title} - {t.assignee_name or '未指派'} (截止: {t.deadline})")
    return "\n".join(lines)

def _team_progress(db: Session) -> str:
    results = db.query(
        Task.assignee_name,
        func.count(Task.id).label("total"),
        func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)).label("done"),
    ).filter(Task.assignee_name != "").group_by(Task.assignee_name).all()
    if not results:
        return "暂无团队任务数据。"
    lines = ["👥 团队进度:"]
    for r in results:
        pct = round(r.done / r.total * 100) if r.total > 0 else 0
        lines.append(f"  • {r.assignee_name}: {r.done}/{r.total} ({pct}%)")
    return "\n".join(lines)

def _daily_report(db: Session) -> str:
    total = db.query(Task).count()
    done_today = db.query(Task).filter(Task.status == TaskStatus.DONE, func.date(Task.updated_at) == date.today()).count()
    overdue = db.query(Task).filter(Task.deadline < date.today(), Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])).count()
    pending = db.query(Task).filter(Task.status == TaskStatus.PENDING).count()
    goals = db.query(Goal).all()
    goal_progress = 0
    if goals:
        progresses = [(g.current_value / g.target_value * 100) if g.target_value > 0 else 0 for g in goals]
        goal_progress = round(sum(progresses) / len(progresses))
    return f"""📊 每日管理简报 ({date.today()})

任务总数: {total}
今日完成: {done_today}
逾期任务: {overdue}
待处理: {pending}
目标达成率: {goal_progress}%"""

def _urge_overdue(db: Session) -> str:
    tasks = db.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).all()
    if not tasks:
        return "当前无需催办的任务。"
    lines = ["📨 催办通知已发送:"]
    for t in tasks:
        lines.append(f"  → {t.assignee_name or '未指派'}: {t.title}")
    return "\n".join(lines)

def _build_data_summary(db: Session) -> str:
    total_tasks = db.query(Task).count()
    overdue = db.query(Task).filter(Task.deadline < date.today(), Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])).count()
    pending = db.query(Task).filter(Task.status == TaskStatus.PENDING).count()
    done = db.query(Task).filter(Task.status == TaskStatus.DONE).count()
    goals = db.query(Goal).limit(5).all()
    goal_text = ", ".join([f"{g.title}({g.current_value}/{g.target_value}{g.unit})" for g in goals]) if goals else "无"
    return f"任务: 总{total_tasks}/完成{done}/待处理{pending}/逾期{overdue}。近期目标: {goal_text}"

COMMAND_MAP = {
    "/今日待办": _today_tasks,
    "/逾期": _overdue_tasks,
    "/团队进度": _team_progress,
    "/日报": _daily_report,
    "/催办": _urge_overdue,
}

async def _ai_response(message: str, db: Session) -> str:
    try:
        from harness.ai_client import ai_client
        from harness.prompt_templates import build_system_prompt, build_context_message
        from harness.context_manager import ContextManager
        from harness.memory_manager import memory_manager
        from harness.sub_agents import sub_agent_runner

        custom_prompt = _get_setting_value(db, "custom_prompt", "")
        role = sub_agent_runner.select_role(message)
        system_prompt = sub_agent_runner.get_system_prompt(role, custom_prompt)
        data_summary = _build_data_summary(db)
        data_context = build_context_message(tasks_summary=data_summary)

        history = memory_manager.get_l1_memory(limit=10)
        ctx_mgr = ContextManager()
        messages = ctx_mgr.build_context(history, system_prompt, data_context)
        messages.append({"role": "user", "content": message})
        messages = ctx_mgr.truncate_if_needed(messages)

        result = await ai_client.chat(messages)
        return result
    except Exception as e:
        return _keyword_fallback(message, db)

def _keyword_fallback(message: str, db: Session) -> str:
    if "任务" in message:
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(5).all()
        if tasks:
            lines = ["最近任务:"]
            for t in tasks:
                s = t.status.value if hasattr(t.status, 'value') else t.status
                lines.append(f"  • {t.title} [{s}] - {t.assignee_name or '未指派'}")
            return "\n".join(lines)
    if "目标" in message:
        goals = db.query(Goal).order_by(Goal.created_at.desc()).limit(5).all()
        if goals:
            lines = ["近期目标:"]
            for g in goals:
                pct = round(g.current_value / g.target_value * 100) if g.target_value > 0 else 0
                lines.append(f"  • {g.title} ({pct}%)")
            return "\n".join(lines)
    if any(kw in message for kw in ["KPI", "kpi", "绩效"]):
        records = db.query(KPIRecord).order_by(KPIRecord.created_at.desc()).limit(5).all()
        if records:
            lines = ["KPI 记录:"]
            for r in records:
                lines.append(f"  • {r.employee_name}: {r.metric_name} = {r.score}分 ({r.grade})")
            return "\n".join(lines)
    if any(kw in message for kw in ["员工", "团队"]):
        emps = db.query(Employee).all()
        if emps:
            lines = [f"员工列表 ({len(emps)} 人):"]
            for e in emps:
                lines.append(f"  • {e.name} - {e.department} {e.position}")
            return "\n".join(lines)
    return "你好！我是千方百计AI管理助手。\n\n可用命令:\n/今日待办 - 查看今日任务\n/逾期 - 查看逾期任务\n/团队进度 - 查看团队完成情况\n/日报 - 生成管理日报\n/催办 - 催办逾期任务\n\n也可以直接问我关于任务、目标、KPI的问题。"

@router.get("/history")
def get_history(db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.id.desc()).limit(50).all()
    return [ConversationOut.model_validate(r) for r in reversed(rows)]

@router.post("/chat")
async def chat(msg: MessageIn, db: Session = Depends(get_db)):
    db.add(Conversation(role="user", content=msg.content, created_at=datetime.utcnow()))
    db.commit()

    text = msg.content.strip()
    handler = COMMAND_MAP.get(text)
    if handler:
        reply = handler(db)
    else:
        reply = await _ai_response(text, db)

    assistant = Conversation(role="assistant", content=reply, created_at=datetime.utcnow())
    db.add(assistant)
    db.commit()
    db.refresh(assistant)
    return ConversationOut.model_validate(assistant)

@router.delete("/history")
def clear_history(db: Session = Depends(get_db)):
    db.query(Conversation).delete()
    db.commit()
    return {"message": "cleared"}
