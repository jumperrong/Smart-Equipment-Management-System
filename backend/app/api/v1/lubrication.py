from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import LubricationPoint, LubricationRecord
from app.schemas import (
    LubricationPointCreate, LubricationPointUpdate, LubricationPointOut,
    LubricationRecordCreate, LubricationRecordOut,
)
from app.services.user_service import get_current_user

router = APIRouter(prefix="/lubrication", tags=["润滑管理"])

# 五定-定时 频次 → 天数映射（用于创建记录后自动推算下次润滑日期）
FREQUENCY_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
}


def _calc_next_date(frequency: Optional[str], base: datetime) -> Optional[datetime]:
    """根据频次推算下次润滑日期；未知频次返回 None。"""
    if not frequency:
        return None
    days = FREQUENCY_DAYS.get(frequency.lower())
    if days is None:
        return None
    return base + timedelta(days=days)


# ============ 润滑点 ============

@router.get("/points", response_model=List[LubricationPointOut])
def list_points(
    equipment_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """润滑点列表，支持 equipment_id 过滤。"""
    q = db.query(LubricationPoint)
    if equipment_id is not None:
        q = q.filter(LubricationPoint.equipment_id == equipment_id)
    if enabled is not None:
        q = q.filter(LubricationPoint.enabled == enabled)
    return q.order_by(LubricationPoint.id.asc()).offset(skip).limit(limit).all()


@router.post("/points", response_model=LubricationPointOut)
def create_point(
    obj_in: LubricationPointCreate,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """创建润滑点（五定卡）。"""
    obj = LubricationPoint(**obj_in.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/points/{point_id}", response_model=LubricationPointOut)
def update_point(
    point_id: int, obj_in: LubricationPointUpdate,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """更新润滑点。"""
    obj = db.query(LubricationPoint).filter(LubricationPoint.id == point_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="润滑点不存在")
    for k, v in obj_in.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/points/{point_id}")
def delete_point(point_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """删除润滑点（级联删除其润滑记录）。"""
    obj = db.query(LubricationPoint).filter(LubricationPoint.id == point_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="润滑点不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True}


class LubricationAlertResponse(BaseModel):
    """润滑告警响应：即将到期 / 已过期。"""
    days: int
    overdue: List[LubricationPointOut] = []
    upcoming: List[LubricationPointOut] = []

    class Config:
        from_attributes = True


@router.get("/points/alerts", response_model=LubricationAlertResponse)
def point_alerts(
    days: int = 7,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """润滑告警：即将到期(默认 7 天内) / 已过期。仅统计 enabled=True 的润滑点。"""
    now = datetime.utcnow()
    soon = now + timedelta(days=days)
    base_q = db.query(LubricationPoint).filter(LubricationPoint.enabled.is_(True))
    overdue = base_q.filter(LubricationPoint.next_lubrication_date < now).all()
    upcoming = base_q.filter(
        LubricationPoint.next_lubrication_date >= now,
        LubricationPoint.next_lubrication_date <= soon,
    ).all()
    return {"days": days, "overdue": overdue, "upcoming": upcoming}


# ============ 润滑记录 ============

@router.get("/records", response_model=List[LubricationRecordOut])
def list_records(
    point_id: Optional[int] = None,
    equipment_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """润滑记录列表，支持 point_id / equipment_id 过滤。"""
    q = db.query(LubricationRecord)
    if point_id is not None:
        q = q.filter(LubricationRecord.point_id == point_id)
    if equipment_id is not None:
        q = q.join(LubricationPoint, LubricationRecord.point_id == LubricationPoint.id).filter(
            LubricationPoint.equipment_id == equipment_id
        )
    return q.order_by(LubricationRecord.lubrication_date.desc(), LubricationRecord.id.desc()).offset(skip).limit(limit).all()


@router.post("/records", response_model=LubricationRecordOut)
def create_record(
    obj_in: LubricationRecordCreate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    """创建润滑执行记录，并根据润滑点频次自动更新其 next_lubrication_date。"""
    point = db.query(LubricationPoint).filter(LubricationPoint.id == obj_in.point_id).first()
    if not point:
        raise HTTPException(status_code=404, detail="润滑点不存在")

    lubrication_date = obj_in.lubrication_date or datetime.utcnow()
    data = obj_in.model_dump()
    data["lubrication_date"] = lubrication_date
    # 执行人快照：未显式提供时回填当前用户
    if data.get("performed_by_id") is None:
        data["performed_by_id"] = current_user.id
    if not data.get("performed_by_name"):
        data["performed_by_name"] = current_user.full_name or current_user.username

    obj = LubricationRecord(**data)
    db.add(obj)

    # 自动推算下次润滑日期
    next_date = _calc_next_date(point.fixed_frequency, lubrication_date)
    if next_date is not None:
        point.next_lubrication_date = next_date
        db.add(point)

    db.commit()
    db.refresh(obj)
    return obj
