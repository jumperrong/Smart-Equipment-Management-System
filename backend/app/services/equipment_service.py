from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Equipment, EquipmentStatus, EquipmentStatusLog, User
from app.schemas import EquipmentCreate, EquipmentUpdate, StatusLogCreate, StatusLogClose


# ---------- Equipment CRUD ----------

def get_equipment(db: Session, eq_id: int) -> Optional[Equipment]:
    return db.query(Equipment).filter(Equipment.id == eq_id).first()


def list_equipments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    factory: Optional[str] = None,
    area: Optional[str] = None,
    status: Optional[EquipmentStatus] = None,
    keyword: Optional[str] = None,
):
    q = db.query(Equipment)
    if factory:
        q = q.filter(Equipment.factory == factory)
    if area:
        q = q.filter(Equipment.area == area)
    if status:
        q = q.filter(Equipment.current_status == status)
    if keyword:
        q = q.filter(
            (Equipment.name.ilike(f"%{keyword}%"))
            | (Equipment.asset_no.ilike(f"%{keyword}%"))
        )
    return q.order_by(Equipment.id.desc()).offset(skip).limit(limit).all()


def create_equipment(db: Session, obj_in: EquipmentCreate) -> Equipment:
    if obj_in.asset_no and db.query(Equipment).filter(Equipment.asset_no == obj_in.asset_no).first():
        raise HTTPException(status_code=400, detail="资产编号已存在")
    db_obj = Equipment(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_equipment(db: Session, db_obj: Equipment, obj_in: EquipmentUpdate) -> Equipment:
    data = obj_in.model_dump(exclude_unset=True)
    if "asset_no" in data and data["asset_no"] and data["asset_no"] != db_obj.asset_no:
        if db.query(Equipment).filter(Equipment.asset_no == data["asset_no"]).first():
            raise HTTPException(status_code=400, detail="资产编号已存在")
    for k, v in data.items():
        setattr(db_obj, k, v)
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_equipment(db: Session, eq_id: int):
    obj = get_equipment(db, eq_id)
    if not obj:
        raise HTTPException(status_code=404, detail="设备不存在")
    db.delete(obj)
    db.commit()


# ---------- Status Log (状态机) ----------

def _close_open_log(db: Session, equipment_id: int, end_at: Optional[datetime] = None):
    """Close any open (end_time is null) status log for the equipment."""
    open_log = (
        db.query(EquipmentStatusLog)
        .filter(
            EquipmentStatusLog.equipment_id == equipment_id,
            EquipmentStatusLog.end_time.is_(None),
        )
        .first()
    )
    if open_log:
        end = end_at or datetime.utcnow()
        open_log.end_time = end
        delta = (end - open_log.start_time).total_seconds() / 60.0
        open_log.duration_minutes = round(delta, 2)
        db.add(open_log)


def change_status(
    db: Session,
    equipment_id: int,
    obj_in: StatusLogCreate,
    operator: User,
) -> EquipmentStatusLog:
    eq = get_equipment(db, equipment_id)
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    # 切换到"其他"状态时必须填写详细原因
    if obj_in.to_status == EquipmentStatus.OTHER and not (
        obj_in.reason_detail and obj_in.reason_detail.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="切换到'其他(OTHER)'状态时必须填写详细原因",
        )
    old_status = eq.current_status
    start = obj_in.start_time or datetime.utcnow()

    _close_open_log(db, equipment_id, end_at=start)

    log = EquipmentStatusLog(
        equipment_id=equipment_id,
        from_status=old_status,
        to_status=obj_in.to_status,
        start_time=start,
        reason_code=obj_in.reason_code,
        reason_detail=obj_in.reason_detail,
        remark=obj_in.remark,
        operator_id=operator.id,
    )
    db.add(log)
    eq.current_status = obj_in.to_status
    eq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(log)
    return log


def close_current_status(
    db: Session,
    equipment_id: int,
    obj_in: StatusLogClose,
) -> EquipmentStatusLog:
    eq = get_equipment(db, equipment_id)
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    open_log = (
        db.query(EquipmentStatusLog)
        .filter(
            EquipmentStatusLog.equipment_id == equipment_id,
            EquipmentStatusLog.end_time.is_(None),
        )
        .first()
    )
    if not open_log:
        raise HTTPException(status_code=400, detail="该设备没有进行中的状态")
    end = obj_in.end_time or datetime.utcnow()
    open_log.end_time = end
    delta = (end - open_log.start_time).total_seconds() / 60.0
    open_log.duration_minutes = round(delta, 2)
    db.commit()
    db.refresh(open_log)
    return open_log


def list_status_logs(
    db: Session,
    equipment_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
):
    q = db.query(EquipmentStatusLog)
    if equipment_id:
        q = q.filter(EquipmentStatusLog.equipment_id == equipment_id)
    return q.order_by(EquipmentStatusLog.id.desc()).offset(skip).limit(limit).all()


def get_current_status_log(db: Session, equipment_id: int) -> Optional[EquipmentStatusLog]:
    return (
        db.query(EquipmentStatusLog)
        .filter(
            EquipmentStatusLog.equipment_id == equipment_id,
            EquipmentStatusLog.end_time.is_(None),
        )
        .first()
    )
