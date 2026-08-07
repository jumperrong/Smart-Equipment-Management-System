from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import EnvironmentLog, Equipment
from app.schemas import EnvironmentLogCreate, EnvironmentLogOut


def list_logs(
    db: Session,
    area: Optional[str] = None,
    factory: Optional[str] = None,
    result: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(EnvironmentLog)
    if area:
        q = q.filter(EnvironmentLog.area == area)
    if factory:
        q = q.filter(EnvironmentLog.factory == factory)
    if result:
        q = q.filter(EnvironmentLog.result == result)
    if start:
        q = q.filter(EnvironmentLog.log_date >= start)
    if end:
        q = q.filter(EnvironmentLog.log_date <= end)
    return q.order_by(EnvironmentLog.log_date.desc()).offset(skip).limit(limit).all()


def get_log(db: Session, log_id: int) -> Optional[EnvironmentLog]:
    return db.query(EnvironmentLog).filter(EnvironmentLog.id == log_id).first()


def create_log(db: Session, obj_in: EnvironmentLogCreate) -> EnvironmentLog:
    log = EnvironmentLog(**obj_in.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def update_log(db: Session, log: EnvironmentLog, obj_in: EnvironmentLogCreate) -> EnvironmentLog:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(log, k, v)
    db.commit()
    db.refresh(log)
    return log


def delete_log(db: Session, log_id: int):
    log = get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="环境核查记录不存在")
    db.delete(log)
    db.commit()
