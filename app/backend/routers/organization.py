"""Organization: employees, teams & coaching routes."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Employee, Team, CoachingRecord, AuditLog
from schemas import (
    EmployeeCreate, EmployeeOut,
    TeamCreate, TeamOut,
    CoachingCreate, CoachingOut,
)

router = APIRouter()

# ── Employees ────────────────────────────────────────────────────────

@router.get("/employees", response_model=List[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).order_by(Employee.created_at.desc()).all()


@router.get("/employees/{emp_id}", response_model=EmployeeOut)
def get_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.post("/employees", response_model=EmployeeOut)
def create_employee(body: EmployeeCreate, db: Session = Depends(get_db)):
    emp = Employee(**body.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@router.put("/employees/{emp_id}", response_model=EmployeeOut)
def update_employee(emp_id: int, body: EmployeeCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/employees/{emp_id}")
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(emp)
    db.commit()
    return {"detail": "deleted"}


# ── Teams ────────────────────────────────────────────────────────────

@router.get("/teams", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db)):
    return db.query(Team).order_by(Team.id).all()


@router.post("/teams", response_model=TeamOut)
def create_team(body: TeamCreate, db: Session = Depends(get_db)):
    team = Team(**body.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.put("/teams/{team_id}", response_model=TeamOut)
def update_team(team_id: int, body: TeamCreate, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(team)
    db.commit()
    return {"detail": "deleted"}


# ── Coaching ─────────────────────────────────────────────────────────

@router.get("/coaching")
def list_coaching(employee_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(CoachingRecord).order_by(CoachingRecord.created_at.desc())
    if employee_id:
        q = q.filter(CoachingRecord.employee_id == employee_id)
    return [CoachingOut.model_validate(c) for c in q.all()]


@router.post("/coaching")
def create_coaching(data: CoachingCreate, db: Session = Depends(get_db)):
    c = CoachingRecord(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    db.add(AuditLog(
        action="coaching_created",
        detail=f"employee_id={c.employee_id}",
        actor="boss",
        resource_type="coaching",
        resource_id=str(c.id),
    ))
    db.commit()
    return CoachingOut.model_validate(c)
