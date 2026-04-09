"""HTTP chat API — invoke AgentLoop for integration tests and scripts."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.database import Database
from app.core.enums import Channel, UserTier
from app.core.models import UnifiedMessage
from app.runtime.agent_loop import AgentLoop

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api-chat"])


class ChatRequest(BaseModel):
    team_id: str = Field(..., description="Team id, e.g. team_ecom")
    message: str = Field(..., min_length=1, description="User message")


class ChatResponse(BaseModel):
    response: str
    metadata: dict = Field(default_factory=dict)


def _user_can_access_team(request: Request, team_id: str) -> bool:
    user = getattr(request.state, "user", None) or {}
    tier = user.get("tier")
    if tier == UserTier.T1.value:
        return True
    teams = getattr(request.state, "user_teams", None) or []
    return team_id in teams


@router.post("/chat", response_model=ChatResponse)
async def post_chat(request: Request, body: ChatRequest) -> ChatResponse:
    if not _user_can_access_team(request, body.team_id):
        raise HTTPException(status_code=403, detail="无权访问该团队")

    db = Database.get_instance()
    team = db.get_by_id("teams", body.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")

    user = getattr(request.state, "user", None) or {}
    emp_id = (user.get("employee_id") or "").strip()
    employee = db.get_by_id("employees", emp_id) if emp_id else None

    message = UnifiedMessage(
        channel=Channel.DASHBOARD,
        sender_id=user.get("id", "dashboard"),
        team_id=body.team_id,
        employee_id=emp_id,
        content=body.message.strip(),
    )

    try:
        loop = AgentLoop(db=db)
        agent_resp = await loop.run(
            message,
            team=team,
            employee=employee,
        )
        return ChatResponse(
            response=agent_resp.content,
            metadata=agent_resp.metadata or {},
        )
    except Exception as exc:
        logger.exception("POST /api/chat failed: %s", exc)
        return ChatResponse(
            response="抱歉，服务暂时不可用，请稍后重试。",
            metadata={"error": str(exc)},
        )
