from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import EquipmentLifecycle
from app.schemas import (
    EquipmentLifecycleCreate, EquipmentLifecycleUpdate, EquipmentLifecycleOut,
)
from app.services.user_service import get_current_user

router = APIRouter(prefix="/equipment-lifecycle", tags=["设备生命周期"])


@router.get("", response_model=List[EquipmentLifecycleOut])
def list_lifecycle(
    equipment_id: Optional[int] = None,
    stage: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """设备生命周期记录列表，支持 equipment_id / stage 过滤。"""
    q = db.query(EquipmentLifecycle)
    if equipment_id is not None:
        q = q.filter(EquipmentLifecycle.equipment_id == equipment_id)
    if stage:
        q = q.filter(EquipmentLifecycle.stage == stage)
    return q.order_by(EquipmentLifecycle.id.desc()).offset(skip).limit(limit).all()


@router.post("", response_model=EquipmentLifecycleOut)
def create_lifecycle(
    obj_in: EquipmentLifecycleCreate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    """创建生命周期阶段记录，自动写入 created_by_id。"""
    obj = EquipmentLifecycle(**obj_in.model_dump(), created_by_id=current_user.id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{lifecycle_id}", response_model=EquipmentLifecycleOut)
def update_lifecycle(
    lifecycle_id: int, obj_in: EquipmentLifecycleUpdate,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """更新生命周期阶段记录。"""
    obj = db.query(EquipmentLifecycle).filter(EquipmentLifecycle.id == lifecycle_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="设备生命周期记录不存在")
    for k, v in obj_in.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{lifecycle_id}")
def delete_lifecycle(lifecycle_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """删除生命周期阶段记录。"""
    obj = db.query(EquipmentLifecycle).filter(EquipmentLifecycle.id == lifecycle_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="设备生命周期记录不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/equipment/{equipment_id}/timeline", response_model=List[EquipmentLifecycleOut])
def equipment_timeline(
    equipment_id: int,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """设备全生命周期时间线：按阶段(T0→T3)及阶段日期升序返回。"""
    return (
        db.query(EquipmentLifecycle)
        .filter(EquipmentLifecycle.equipment_id == equipment_id)
        .order_by(EquipmentLifecycle.stage.asc(), EquipmentLifecycle.stage_date.asc(), EquipmentLifecycle.id.asc())
        .all()
    )
