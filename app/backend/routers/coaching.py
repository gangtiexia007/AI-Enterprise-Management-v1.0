from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import CoachingRecord, AuditLog
from schemas import CoachingCreate, CoachingOut
from typing import Optional

router = APIRouter()

@router.get("")
def list_coaching(employee_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(CoachingRecord).order_by(CoachingRecord.created_at.desc())
    if employee_id:
        q = q.filter(CoachingRecord.employee_id == employee_id)
    return [CoachingOut.model_validate(c) for c in q.all()]

@router.post("")
def create_coaching(data: CoachingCreate, db: Session = Depends(get_db)):
    c = CoachingRecord(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    db.add(AuditLog(action="coaching_created", detail=f"employee_id={c.employee_id}", actor="boss", resource_type="coaching", resource_id=str(c.id)))
    db.commit()
    return CoachingOut.model_validate(c)
