from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import AuditLog
from schemas import AuditLogOut
from typing import Optional

router = APIRouter()

@router.get("")
def list_audit_logs(action: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        q = q.filter(AuditLog.action.contains(action))
    return [AuditLogOut.model_validate(a) for a in q.limit(limit).all()]
