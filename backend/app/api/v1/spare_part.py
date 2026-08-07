from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import EquipmentSparePart, UserRole
from app.schemas import (
    SparePartCreate, SparePartOut, SparePartUpdate, StockMovement, MovementOut,
    EquipmentSparePartCreate, EquipmentSparePartOut, SparePartStockSummary,
)
from app.services import spare_part_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/spare-parts", tags=["备件管理"])


@router.get("", response_model=list[SparePartOut])
def list_parts(
    keyword: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return spare_part_service.list_parts(db, keyword=keyword, skip=skip, limit=limit)


@router.get("/stock/summary", response_model=SparePartStockSummary)
def stock_summary(
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    """备件库存概览（总品种、总库存、总金额、低库存、断货数）。"""
    return spare_part_service.get_stock_summary(db)


@router.get("/movements/all", response_model=list[MovementOut])
def list_all_movements(
    keyword: Optional[str] = None,
    movement_type: Optional[str] = None,
    ref_type: Optional[str] = None,
    skip: int = 0, limit: int = 200,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    """全局出入库流水查询（跨备件，支持按关键字/类型/来源筛选）。"""
    return spare_part_service.list_all_movements(
        db, keyword=keyword, movement_type=movement_type,
        ref_type=ref_type, skip=skip, limit=limit,
    )


@router.get("/{part_id}", response_model=SparePartOut)
def get_part(part_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = spare_part_service.get_part(db, part_id)
    if not obj:
        raise HTTPException(status_code=404, detail="备件不存在")
    return obj


@router.post("", response_model=SparePartOut, dependencies=[Depends(require_permission("spare_part.write"))])
def create_part(obj_in: SparePartCreate, db: Session = Depends(get_db)):
    return spare_part_service.create_part(db, obj_in)


@router.put("/{part_id}", response_model=SparePartOut, dependencies=[Depends(require_permission("spare_part.write"))])
def update_part(part_id: int, obj_in: SparePartUpdate, db: Session = Depends(get_db)):
    obj = spare_part_service.get_part(db, part_id)
    if not obj:
        raise HTTPException(status_code=404, detail="备件不存在")
    return spare_part_service.update_part(db, obj, obj_in)


@router.delete("/{part_id}", dependencies=[Depends(require_permission("spare_part.delete"))])
def delete_part(part_id: int, db: Session = Depends(get_db)):
    spare_part_service.delete_part(db, part_id)
    return {"ok": True}


@router.post("/{part_id}/movement", response_model=MovementOut, dependencies=[Depends(require_permission("spare_part.movement"))])
def move_stock(
    part_id: int, obj_in: StockMovement,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return spare_part_service.move_stock(db, part_id, obj_in, operator_id=current_user.id)


@router.get("/{part_id}/movements", response_model=list[MovementOut])
def list_movements(part_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return spare_part_service.list_movements(db, part_id=part_id, skip=skip, limit=limit)


@router.get("/{part_id}/equipments", response_model=list[EquipmentSparePartOut])
def list_equipment_parts_of_part(part_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from app.models import EquipmentSparePart
    return db.query(EquipmentSparePart).filter(EquipmentSparePart.spare_part_id == part_id).all()


# 设备易损件关联（嵌套在 equipment 路径下）
equipment_router = APIRouter(prefix="/equipments/{eq_id}/spare-parts", tags=["设备易损件清单"])


@equipment_router.get("", response_model=list[EquipmentSparePartOut])
def list_eq_parts(eq_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return spare_part_service.list_equipment_parts(db, eq_id)


@equipment_router.post("", response_model=EquipmentSparePartOut, dependencies=[Depends(require_permission("spare_part.equipment_bind"))])
def add_eq_part(eq_id: int, obj_in: EquipmentSparePartCreate, db: Session = Depends(get_db)):
    return spare_part_service.add_equipment_part(db, eq_id, obj_in)


@equipment_router.delete("/{spare_part_id}", dependencies=[Depends(require_permission("spare_part.equipment_bind"))])
def remove_eq_part(eq_id: int, spare_part_id: int, db: Session = Depends(get_db)):
    spare_part_service.remove_equipment_part(db, eq_id, spare_part_id)
    return {"ok": True}


# 注意：equipment_router 不在此处 include 到 router，
# 而是直接在顶层 api_router 注册，避免前缀叠加成 /spare-parts/equipments/{eq_id}/spare-parts
