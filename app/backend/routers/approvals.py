from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Approval, ApprovalStatus, AuditLog
from schemas import ApprovalCreate, ApprovalOut
from datetime import datetime
from typing import Optional

router = APIRouter()

@router.get("")
def list_approvals(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Approval).order_by(Approval.created_at.desc())
    if status:
        q = q.filter(Approval.status == status)
    return [ApprovalOut.model_validate(a) for a in q.all()]

@router.get("/{approval_id}")
def get_approval(approval_id: int, db: Session = Depends(get_db)):
    a = db.query(Approval).filter(Approval.id == approval_id).first()
    if not a:
        raise HTTPException(404, "Approval not found")
    return ApprovalOut.model_validate(a)

@router.post("")
def create_approval(data: ApprovalCreate, db: Session = Depends(get_db)):
    a = Approval(**data.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    db.add(AuditLog(action="approval_created", detail=f"title={a.title}", actor="system", resource_type="approval", resource_id=str(a.id)))
    db.commit()
    return ApprovalOut.model_validate(a)

@router.post("/{approval_id}/approve")
def approve(approval_id: int, db: Session = Depends(get_db)):
    a = db.query(Approval).filter(Approval.id == approval_id).first()
    if not a:
        raise HTTPException(404, "Not found")
    a.status = ApprovalStatus.APPROVED
    a.resolved_at = datetime.utcnow()
    a.resolved_by = "boss"
    db.add(AuditLog(action="approval_approved", detail=f"id={a.id}, title={a.title}", actor="boss", resource_type="approval", resource_id=str(a.id)))
    db.commit()
    return ApprovalOut.model_validate(a)

@router.post("/{approval_id}/reject")
def reject(approval_id: int, db: Session = Depends(get_db)):
    a = db.query(Approval).filter(Approval.id == approval_id).first()
    if not a:
        raise HTTPException(404, "Not found")
    a.status = ApprovalStatus.REJECTED
    a.resolved_at = datetime.utcnow()
    a.resolved_by = "boss"
    db.add(AuditLog(action="approval_rejected", detail=f"id={a.id}, title={a.title}", actor="boss", resource_type="approval", resource_id=str(a.id)))
    db.commit()
    return ApprovalOut.model_validate(a)
