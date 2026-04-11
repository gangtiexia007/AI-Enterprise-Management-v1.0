"""Multi-Agent system API endpoints."""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AgentRun, Knowledge, KnowledgeCategory

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Request / Response schemas ----------

class MultiAgentChatRequest(BaseModel):
    message: str
    platform: str = ""
    market: str = ""
    store_id: str = ""
    niche: str = ""
    target_persona: str = ""
    design_concept: str = ""
    business_line: str = ""
    language_style: str = ""
    data: Optional[dict] = None
    constraints: Optional[dict] = None
    history: Optional[dict] = None
    attachments: list[str] = []


class MultiAgentChatResponse(BaseModel):
    run_id: str = ""
    task_type: str = ""
    response: str = ""


class AgentRunOut(BaseModel):
    id: int
    run_id: str
    task_type: str
    route_name: str
    agents_called: list[str] = []
    input_summary: str
    final_output: str
    total_tokens: int
    duration_ms: int
    data_sufficiency: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class AgentMemoryEntryCreate(BaseModel):
    memory_type: str = ""
    title: str = ""
    content: str = ""
    level: int = 3
    platform: str = ""
    market: str = ""
    persona: str = ""
    niche: str = ""
    conditions: str = "[]"
    action: str = ""
    result: str = ""
    why: str = ""
    reusable: int = 1
    source_run_id: str = ""


class AgentMemoryEntryOut(BaseModel):
    id: int
    memory_type: str
    title: str
    content: str = ""
    level: int = 3
    platform: str
    market: str
    persona: str
    niche: str
    conditions: str
    action: str
    result: str
    why: str
    reusable: int
    source_run_id: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Endpoints ----------

@router.post("/chat", response_model=MultiAgentChatResponse)
async def multi_agent_chat(req: MultiAgentChatRequest, db: Session = Depends(get_db)):
    from harness.multi_agent.orchestrator import orchestrator

    extra_data: dict = {}
    if req.platform:
        extra_data["platform"] = req.platform
    if req.market:
        extra_data["market"] = req.market
    if req.store_id:
        extra_data["store_id"] = req.store_id
    if req.niche:
        extra_data["niche"] = req.niche
    if req.target_persona:
        extra_data["target_persona"] = req.target_persona
    if req.design_concept:
        extra_data["design_concept"] = req.design_concept
    if req.business_line:
        extra_data["business_line"] = req.business_line
    if req.language_style:
        extra_data["language_style"] = req.language_style
    if req.data:
        extra_data["data"] = req.data
    if req.constraints:
        extra_data["constraints"] = req.constraints
    if req.history:
        extra_data["history"] = req.history
    if req.attachments:
        extra_data["attachments"] = req.attachments

    response_text = await orchestrator.run(req.message, db, extra_data=extra_data or None)

    last_run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
    run_id = last_run.run_id if last_run else ""
    task_type = last_run.task_type if last_run else ""

    return MultiAgentChatResponse(
        run_id=run_id,
        task_type=task_type,
        response=response_text,
    )


@router.get("/runs")
def list_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.query(AgentRun).count()
    rows = db.query(AgentRun).order_by(AgentRun.id.desc()).offset(skip).limit(limit).all()
    items = []
    for r in rows:
        try:
            agents = json.loads(r.agents_called) if r.agents_called else []
        except (json.JSONDecodeError, TypeError):
            agents = []
        items.append(AgentRunOut(
            id=r.id,
            run_id=r.run_id,
            task_type=r.task_type or "",
            route_name=r.route_name or "",
            agents_called=agents,
            input_summary=r.input_summary or "",
            final_output=r.final_output or "",
            total_tokens=r.total_tokens or 0,
            duration_ms=r.duration_ms or 0,
            data_sufficiency=r.data_sufficiency or "",
            created_at=r.created_at.isoformat() if r.created_at else None,
        ))
    return {"total": total, "items": items}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    row = db.query(AgentRun).filter(AgentRun.run_id == run_id).first()
    if not row:
        return {"error": "Run not found"}
    try:
        agents = json.loads(row.agents_called) if row.agents_called else []
    except (json.JSONDecodeError, TypeError):
        agents = []
    return AgentRunOut(
        id=row.id,
        run_id=row.run_id,
        task_type=row.task_type or "",
        route_name=row.route_name or "",
        agents_called=agents,
        input_summary=row.input_summary or "",
        final_output=row.final_output or "",
        total_tokens=row.total_tokens or 0,
        duration_ms=row.duration_ms or 0,
        data_sufficiency=row.data_sufficiency or "",
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


@router.get("/config")
def get_agent_configs(db: Session = Depends(get_db)):
    from harness.multi_agent.orchestrator import orchestrator
    from models import Setting
    configs = orchestrator.get_agent_configs()
    for cfg in configs:
        key = f"agent_enabled_{cfg['agent_id']}"
        s = db.query(Setting).filter(Setting.key == key).first()
        if s:
            cfg["enabled"] = s.value == "true"
    return configs


@router.get("/memory")
def list_memory(
    memory_type: Optional[str] = None,
    level: Optional[int] = None,
    platform: Optional[str] = None,
    market: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Knowledge)
    if memory_type:
        query = query.filter(Knowledge.memory_type == memory_type)
    if level is not None:
        query = query.filter(Knowledge.level == level)
    if platform:
        query = query.filter(Knowledge.platform == platform)
    if market:
        query = query.filter(Knowledge.market == market)

    total = query.count()
    rows = query.order_by(Knowledge.id.desc()).offset(skip).limit(limit).all()
    items = [
        AgentMemoryEntryOut(
            id=r.id,
            memory_type=r.memory_type or "",
            title=r.title or "",
            content=r.content or "",
            level=r.level if r.level is not None else 3,
            platform=r.platform or "",
            market=r.market or "",
            persona=r.persona or "",
            niche=r.niche or "",
            conditions=r.conditions or "[]",
            action=r.action or "",
            result=r.result or "",
            why=r.why or "",
            reusable=r.reusable if r.reusable is not None else 1,
            source_run_id=r.source_run_id or "",
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    return {"total": total, "items": items}


@router.post("/memory")
def create_memory(entry: AgentMemoryEntryCreate, db: Session = Depends(get_db)):
    category_map = {
        "sop": KnowledgeCategory.SOP,
        "case": KnowledgeCategory.CASE,
        "rule": KnowledgeCategory.RULE,
        "taboo": KnowledgeCategory.TABOO,
    }
    cat = category_map.get(entry.memory_type.lower(), KnowledgeCategory.CASE)

    record = Knowledge(
        title=entry.title,
        content=entry.content,
        category=cat,
        source="multi_agent",
        level=entry.level,
        memory_type=entry.memory_type,
        platform=entry.platform,
        market=entry.market,
        persona=entry.persona,
        niche=entry.niche,
        conditions=entry.conditions,
        action=entry.action,
        result=entry.result,
        why=entry.why,
        reusable=entry.reusable,
        source_run_id=entry.source_run_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return AgentMemoryEntryOut(
        id=record.id,
        memory_type=record.memory_type or "",
        title=record.title or "",
        content=record.content or "",
        level=record.level if record.level is not None else 3,
        platform=record.platform or "",
        market=record.market or "",
        persona=record.persona or "",
        niche=record.niche or "",
        conditions=record.conditions or "[]",
        action=record.action or "",
        result=record.result or "",
        why=record.why or "",
        reusable=record.reusable if record.reusable is not None else 1,
        source_run_id=record.source_run_id or "",
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


class AgentToggleRequest(BaseModel):
    enabled: bool


@router.put("/config/{agent_id}")
def toggle_agent(agent_id: str, req: AgentToggleRequest, db: Session = Depends(get_db)):
    from models import Setting
    key = f"agent_enabled_{agent_id}"
    s = db.query(Setting).filter(Setting.key == key).first()
    if s:
        s.value = str(req.enabled).lower()
    else:
        db.add(Setting(key=key, value=str(req.enabled).lower()))
    db.commit()
    return {"agent_id": agent_id, "enabled": req.enabled}
