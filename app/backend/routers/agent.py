"""Agent chat router — delegates to AgentLoop state machine."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models import Conversation, Setting, AuditLog
from schemas import MessageIn, ConversationOut

router = APIRouter()


def _get_agent_mode(db: Session) -> str:
    s = db.query(Setting).filter(Setting.key == "agent_mode").first()
    if s and s.value in ("command", "light", "full"):
        return s.value
    from models import Agent
    agent = db.query(Agent).first()
    if agent:
        return agent.mode.value if hasattr(agent.mode, 'value') else agent.mode
    return "full"


def _log_audit(db: Session, action: str, detail: str = ""):
    db.add(AuditLog(action=action, detail=detail, actor="agent", resource_type="conversation"))
    db.commit()


@router.get("/history")
def get_history(db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.id.desc()).limit(50).all()
    return [ConversationOut.model_validate(r) for r in reversed(rows)]


@router.post("/chat")
async def chat(msg: MessageIn, db: Session = Depends(get_db)):
    db.add(Conversation(role="user", content=msg.content, created_at=datetime.utcnow()))
    db.commit()

    text = msg.content.strip()
    mode = _get_agent_mode(db)

    if text.startswith("/") and mode != "full":
        mode = "command"

    from harness.agent_loop import AgentLoop
    loop = AgentLoop()
    reply = await loop.run(text, db_session=db, agent_mode=mode)

    assistant = Conversation(role="assistant", content=reply, created_at=datetime.utcnow())
    db.add(assistant)
    db.commit()
    db.refresh(assistant)

    _log_audit(db, "agent_chat", f"mode={mode} input={text[:100]}")
    return ConversationOut.model_validate(assistant)


@router.delete("/history")
def clear_history(db: Session = Depends(get_db)):
    db.query(Conversation).delete()
    db.commit()
    return {"message": "cleared"}
