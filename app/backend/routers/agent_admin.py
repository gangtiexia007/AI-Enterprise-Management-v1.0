"""Agent administration: Agent config, SubAgents, Skills CRUD."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Agent, SubAgentModel, Skill, AgentSkill, AuditLog
from schemas import (
    AgentCreate, AgentUpdate, AgentOut,
    SubAgentCreate, SubAgentUpdate, SubAgentOut,
    SkillCreate, SkillUpdate, SkillOut,
)
from datetime import datetime

router = APIRouter()


# ───────── Agent Config ─────────

@router.get("/config", response_model=AgentOut)
def get_agent_config(db: Session = Depends(get_db)):
    agent = db.query(Agent).first()
    if not agent:
        agent = Agent(
            name="千方百计AI",
            description="老板私人管理助手",
            model_primary="gpt-4o-mini",
            model_fallback="gpt-3.5-turbo",
            mode="full",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
    return agent


@router.put("/config", response_model=AgentOut)
def update_agent_config(data: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(Agent).first()
    if not agent:
        agent = Agent(name="千方百计AI")
        db.add(agent)
        db.commit()
        db.refresh(agent)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(agent, k, v)
    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    return agent


# ───────── Sub-Agents ─────────

@router.get("/sub-agents", response_model=list[SubAgentOut])
def list_sub_agents(db: Session = Depends(get_db)):
    from harness.sub_agents import sub_agent_manager
    sub_agent_manager.ensure_defaults_in_db(db)
    return db.query(SubAgentModel).all()


@router.post("/sub-agents", response_model=SubAgentOut)
def create_sub_agent(data: SubAgentCreate, db: Session = Depends(get_db)):
    sa = SubAgentModel(**data.model_dump())
    db.add(sa)
    db.commit()
    db.refresh(sa)
    db.add(AuditLog(action="create_sub_agent", detail=f"Created sub-agent: {sa.name}", actor="admin", resource_type="sub_agent", resource_id=str(sa.id)))
    db.commit()
    return sa


@router.put("/sub-agents/{sa_id}", response_model=SubAgentOut)
def update_sub_agent(sa_id: int, data: SubAgentUpdate, db: Session = Depends(get_db)):
    sa = db.query(SubAgentModel).filter(SubAgentModel.id == sa_id).first()
    if not sa:
        raise HTTPException(404, "Sub-agent not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sa, k, v)
    db.commit()
    db.refresh(sa)
    return sa


@router.delete("/sub-agents/{sa_id}")
def delete_sub_agent(sa_id: int, db: Session = Depends(get_db)):
    sa = db.query(SubAgentModel).filter(SubAgentModel.id == sa_id).first()
    if not sa:
        raise HTTPException(404, "Sub-agent not found")
    db.delete(sa)
    db.add(AuditLog(action="delete_sub_agent", detail=f"Deleted sub-agent: {sa.name}", actor="admin", resource_type="sub_agent", resource_id=str(sa_id)))
    db.commit()
    return {"message": "deleted"}


# ───────── Skills ─────────

@router.get("/skills", response_model=list[SkillOut])
def list_skills(skill_type: str = "", db: Session = Depends(get_db)):
    _sync_builtin_skills(db)
    q = db.query(Skill)
    if skill_type:
        q = q.filter(Skill.type == skill_type)
    return q.order_by(Skill.type, Skill.name).all()


@router.post("/skills", response_model=SkillOut)
def create_skill(data: SkillCreate, db: Session = Depends(get_db)):
    existing = db.query(Skill).filter(Skill.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Skill '{data.name}' already exists")
    skill = Skill(**data.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)

    from harness.skill_registry import skill_registry
    if skill.type.value if hasattr(skill.type, 'value') else skill.type == "custom":
        config = json.loads(skill.config) if skill.config else {}
        skill_registry.register_custom_skill(skill.name, skill.description, config.get("content", ""), skill.permission_level)
    elif skill.type.value if hasattr(skill.type, 'value') else skill.type == "mcp":
        config = json.loads(skill.config) if skill.config else {}
        skill_registry.register_mcp_skill(skill.name, skill.description, config.get("endpoint", ""), config.get("auth", {}), skill.permission_level)

    db.add(AuditLog(action="create_skill", detail=f"Created skill: {skill.name} ({skill.type})", actor="admin", resource_type="skill", resource_id=str(skill.id)))
    db.commit()
    return skill


@router.put("/skills/{skill_id}", response_model=SkillOut)
def update_skill(skill_id: int, data: SkillUpdate, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(skill, k, v)
    skill.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: int, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    stype = skill.type.value if hasattr(skill.type, 'value') else skill.type
    if stype == "builtin":
        raise HTTPException(400, "Cannot delete builtin skills")
    from harness.skill_registry import skill_registry
    skill_registry.unregister(skill.name)
    db.delete(skill)
    db.add(AuditLog(action="delete_skill", detail=f"Deleted skill: {skill.name}", actor="admin", resource_type="skill", resource_id=str(skill_id)))
    db.commit()
    return {"message": "deleted"}


@router.post("/skills/{skill_id}/toggle")
def toggle_skill(skill_id: int, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    skill.enabled = 0 if skill.enabled else 1
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "name": skill.name, "enabled": skill.enabled}


@router.get("/skills/{skill_id}/test")
async def test_skill(skill_id: int, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    from harness.skill_registry import skill_registry
    result = await skill_registry.execute(skill.name, {}, db_session=db)
    return {"skill": skill.name, "success": result.success, "data": result.data, "error": result.error}


def _sync_builtin_skills(db: Session):
    """Ensure all registered builtin skills have a DB row."""
    from harness.skill_registry import skill_registry
    for sd in skill_registry.list_skills(skill_type="builtin"):
        existing = db.query(Skill).filter(Skill.name == sd.name).first()
        if not existing:
            db.add(Skill(
                name=sd.name,
                type="builtin",
                description=sd.description,
                config="{}",
                enabled=1,
                permission_level=sd.permission_level,
            ))
    db.commit()
