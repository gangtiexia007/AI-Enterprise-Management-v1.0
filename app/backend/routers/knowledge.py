from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Knowledge
from schemas import KnowledgeCreate, KnowledgeUpdate, KnowledgeOut

router = APIRouter()


@router.get("", response_model=List[KnowledgeOut])
def list_knowledge(category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Knowledge)
    if category:
        q = q.filter(Knowledge.category == category)
    return q.order_by(Knowledge.created_at.desc()).all()


@router.get("/{item_id}", response_model=KnowledgeOut)
def get_knowledge(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Knowledge).filter(Knowledge.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.post("", response_model=KnowledgeOut)
def create_knowledge(body: KnowledgeCreate, db: Session = Depends(get_db)):
    item = Knowledge(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=KnowledgeOut)
def update_knowledge(item_id: int, body: KnowledgeUpdate, db: Session = Depends(get_db)):
    item = db.query(Knowledge).filter(Knowledge.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_knowledge(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Knowledge).filter(Knowledge.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    db.delete(item)
    db.commit()
    return {"detail": "deleted"}
