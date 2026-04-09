from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Goal
from schemas import GoalCreate, GoalUpdate, GoalOut

router = APIRouter()


def _build_tree(goals: list, parent_id=None) -> list:
    """Recursively build a tree of goals."""
    tree = []
    for g in goals:
        if g.parent_id == parent_id:
            node = GoalOut.model_validate(g)
            node.children = _build_tree(goals, g.id)
            if g.target_value and g.target_value > 0:
                node.progress = round(g.current_value / g.target_value * 100, 1)
            tree.append(node)
    return tree


@router.get("", response_model=List[GoalOut])
def list_goals(db: Session = Depends(get_db)):
    all_goals = db.query(Goal).order_by(Goal.created_at.desc()).all()
    return _build_tree(all_goals, parent_id=None)


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    all_goals = db.query(Goal).all()
    node = GoalOut.model_validate(goal)
    node.children = _build_tree(all_goals, goal.id)
    if goal.target_value and goal.target_value > 0:
        node.progress = round(goal.current_value / goal.target_value * 100, 1)
    return node


@router.post("", response_model=GoalOut)
def create_goal(body: GoalCreate, db: Session = Depends(get_db)):
    goal = Goal(**body.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    out = GoalOut.model_validate(goal)
    if goal.target_value and goal.target_value > 0:
        out.progress = round(goal.current_value / goal.target_value * 100, 1)
    return out


@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, body: GoalUpdate, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    out = GoalOut.model_validate(goal)
    if goal.target_value and goal.target_value > 0:
        out.progress = round(goal.current_value / goal.target_value * 100, 1)
    return out


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return {"detail": "deleted"}
