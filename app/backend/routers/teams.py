"""Teams management router."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Team
from schemas import TeamCreate, TeamOut

router = APIRouter()


@router.get("", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db)):
    return db.query(Team).order_by(Team.id).all()


@router.post("", response_model=TeamOut)
def create_team(body: TeamCreate, db: Session = Depends(get_db)):
    team = Team(**body.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.put("/{team_id}", response_model=TeamOut)
def update_team(team_id: int, body: TeamCreate, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(team)
    db.commit()
    return {"detail": "deleted"}
