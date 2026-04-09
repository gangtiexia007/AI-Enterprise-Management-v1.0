from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Setting
from schemas import SettingItem, SettingOut

router = APIRouter()

DEFAULTS = {
    "company_name": "千方百计AI",
    "model_primary": "gpt-4o",
    "model_fallback": "gpt-3.5-turbo",
    "feishu_app_id": "",
    "feishu_app_secret": "",
    "custom_prompt": "你是老板的管理助手，帮助老板高效管理企业。",
    "escalation_intervals": "30,60,120",
    "report_time": "09:00",
}


@router.get("", response_model=List[SettingOut])
def list_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()


@router.get("/{key}", response_model=SettingOut)
def get_setting(key: str, db: Session = Depends(get_db)):
    s = db.query(Setting).filter(Setting.key == key).first()
    if not s:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return s


@router.put("", response_model=SettingOut)
def upsert_setting(body: SettingItem, db: Session = Depends(get_db)):
    s = db.query(Setting).filter(Setting.key == body.key).first()
    if s:
        s.value = body.value
    else:
        s = Setting(key=body.key, value=body.value)
        db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.post("/init")
def init_defaults(db: Session = Depends(get_db)):
    created = []
    for key, value in DEFAULTS.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if not existing:
            db.add(Setting(key=key, value=value))
            created.append(key)
    db.commit()
    return {"detail": f"Initialized {len(created)} settings", "keys": created}
