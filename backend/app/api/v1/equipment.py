from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import EquipmentStatus, UserRole
from app.schemas import (
    EquipmentCreate, EquipmentOut, EquipmentUpdate,
    StatusLogCreate, StatusLogOut, StatusLogClose,
)
from app.services import equipment_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/equipments", tags=["设备管理"])


@router.get("", response_model=list[EquipmentOut])
def list_equipments(
    skip: int = 0,
    limit: int = 100,
    factory: Optional[str] = None,
    area: Optional[str] = None,
    status: Optional[EquipmentStatus] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return equipment_service.list_equipments(
        db, skip=skip, limit=limit, factory=factory, area=area, status=status, keyword=keyword
    )


@router.post("", response_model=EquipmentOut, dependencies=[Depends(require_permission("equipment.write"))])
def create_equipment(obj_in: EquipmentCreate, db: Session = Depends(get_db)):
    return equipment_service.create_equipment(db, obj_in)


@router.get("/{eq_id}", response_model=EquipmentOut)
def get_equipment(eq_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = equipment_service.get_equipment(db, eq_id)
    if not obj:
        raise HTTPException(status_code=404, detail="设备不存在")
    return obj


@router.put("/{eq_id}", response_model=EquipmentOut, dependencies=[Depends(require_permission("equipment.write"))])
def update_equipment(eq_id: int, obj_in: EquipmentUpdate, db: Session = Depends(get_db)):
    db_obj = equipment_service.get_equipment(db, eq_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="设备不存在")
    return equipment_service.update_equipment(db, db_obj, obj_in)


@router.delete("/{eq_id}", dependencies=[Depends(require_permission("equipment.delete"))])
def delete_equipment(eq_id: int, db: Session = Depends(get_db)):
    equipment_service.delete_equipment(db, eq_id)
    return {"ok": True}


# ---------- Status ----------

@router.post("/{eq_id}/status", response_model=StatusLogOut)
def change_status(
    eq_id: int,
    obj_in: StatusLogCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("equipment.change_status")),
):
    return equipment_service.change_status(db, eq_id, obj_in, current_user)


@router.post("/{eq_id}/status/close", response_model=StatusLogOut, dependencies=[Depends(require_permission("equipment.change_status"))])
def close_status(eq_id: int, obj_in: StatusLogClose, db: Session = Depends(get_db)):
    return equipment_service.close_current_status(db, eq_id, obj_in)


@router.get("/{eq_id}/status/logs", response_model=list[StatusLogOut])
def list_status_logs(eq_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return equipment_service.list_status_logs(db, equipment_id=eq_id, skip=skip, limit=limit)


@router.get("/{eq_id}/status/current", response_model=Optional[StatusLogOut])
def get_current_status(eq_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return equipment_service.get_current_status_log(db, eq_id)
