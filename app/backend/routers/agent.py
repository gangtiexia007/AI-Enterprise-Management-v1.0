"""Agent chat router — delegates to AgentLoop state machine."""
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from database import get_db
from models import Conversation, Setting, AuditLog
from schemas import MessageIn, ConversationOut


class ChatRequest(BaseModel):
    message: str

router = APIRouter()


def _get_agent_mode(db: Session) -> str:
    s = db.query(Setting).filter(Setting.key == "agent_mode").first()
    if s and s.value in ("command", "light", "full", "multi_agent"):
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


@router.post("/chat-stream")
async def agent_chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """Stream agent response via SSE."""
    from harness.ai_client import ai_client
    from harness.agent_loop import AgentLoop

    db.add(Conversation(role="user", content=req.message, created_at=datetime.utcnow()))
    db.commit()

    agent_mode = _get_agent_mode(db)
    if agent_mode in ("multi_agent", "command"):
        loop = AgentLoop()
        result = await loop.run(req.message, db_session=db, agent_mode=agent_mode)
        db.add(Conversation(role="assistant", content=result, created_at=datetime.utcnow()))
        db.commit()

        async def single_event():
            yield f"data: {json.dumps({'content': result, 'done': True}, ensure_ascii=False)}\n\n"

        return StreamingResponse(single_event(), media_type="text/event-stream")

    async def generate():
        from harness.prompt_templates import build_system_prompt
        from harness.context_manager import ContextManager
        from harness.memory_manager import memory_manager

        custom_prompt = ""
        s = db.query(Setting).filter(Setting.key == "custom_prompt").first()
        if s:
            custom_prompt = s.value
        industry = ""
        ind_s = db.query(Setting).filter(Setting.key == "industry_preset").first()
        if ind_s:
            industry = ind_s.value

        system_prompt = build_system_prompt("director", custom_prompt, industry=industry)
        history = memory_manager.get_l1_memory(limit=10)
        ctx_mgr = ContextManager()
        messages = ctx_mgr.build_context(history, system_prompt, "")
        messages.append({"role": "user", "content": req.message})
        messages = ctx_mgr.truncate_if_needed(messages)

        full_content = ""
        try:
            async for chunk in ai_client.chat_stream(messages):
                full_content += chunk
                yield f"data: {json.dumps({'content': chunk, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'content': '', 'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'content': f'Error: {str(e)}', 'done': True}, ensure_ascii=False)}\n\n"
            full_content = f"Error: {str(e)}"

        db.add(Conversation(role="assistant", content=full_content, created_at=datetime.utcnow()))
        db.commit()

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/history")
def clear_history(db: Session = Depends(get_db)):
    db.query(Conversation).delete()
    db.commit()
    return {"message": "cleared"}
