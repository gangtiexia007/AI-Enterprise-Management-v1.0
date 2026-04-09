from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import KPIRecord
from schemas import KPICreate, KPIUpdate, KPIOut

router = APIRouter()


def _calc_grade(score: float) -> str:
    if score >= 120:
        return "S"
    elif score >= 100:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 60:
        return "C"
    return "D"


@router.get("", response_model=List[KPIOut])
def list_kpi(
    employee_id: Optional[int] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(KPIRecord)
    if employee_id:
        q = q.filter(KPIRecord.employee_id == employee_id)
    if period:
        q = q.filter(KPIRecord.period == period)
    return q.order_by(KPIRecord.created_at.desc()).all()


@router.get("/summary")
def kpi_summary(db: Session = Depends(get_db)):
    rows = (
        db.query(
            KPIRecord.employee_id,
            KPIRecord.employee_name,
            func.avg(KPIRecord.score).label("avg_score"),
            func.count(KPIRecord.id).label("record_count"),
        )
        .group_by(KPIRecord.employee_id, KPIRecord.employee_name)
        .all()
    )
    return [
        {
            "employee_id": r.employee_id,
            "employee_name": r.employee_name,
            "avg_score": round(r.avg_score, 1) if r.avg_score else 0,
            "record_count": r.record_count,
        }
        for r in rows
    ]


@router.post("", response_model=KPIOut)
def create_kpi(body: KPICreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    score = 0.0
    if data["target_value"] > 0:
        score = round(data["actual_value"] / data["target_value"] * 100, 1)
    grade = _calc_grade(score)
    record = KPIRecord(**data, score=score, grade=grade)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/{record_id}", response_model=KPIOut)
def update_kpi(record_id: int, body: KPIUpdate, db: Session = Depends(get_db)):
    record = db.query(KPIRecord).filter(KPIRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="KPI record not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    if record.target_value and record.target_value > 0:
        record.score = round(record.actual_value / record.target_value * 100, 1)
        record.grade = _calc_grade(record.score)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{record_id}")
def delete_kpi(record_id: int, db: Session = Depends(get_db)):
    record = db.query(KPIRecord).filter(KPIRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="KPI record not found")
    db.delete(record)
    db.commit()
    return {"detail": "deleted"}
