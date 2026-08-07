from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import SparePart, SparePartMovement, EquipmentSparePart
from app.schemas import (
    SparePartCreate, SparePartUpdate, StockMovement,
    EquipmentSparePartCreate,
)


def get_part(db: Session, part_id: int) -> Optional[SparePart]:
    return db.query(SparePart).filter(SparePart.id == part_id).first()


def get_part_by_sku(db: Session, sku: str) -> Optional[SparePart]:
    return db.query(SparePart).filter(SparePart.sku == sku).first()


def list_parts(db: Session, keyword: Optional[str] = None, skip: int = 0, limit: int = 100):
    q = db.query(SparePart)
    if keyword:
        q = q.filter(
            (SparePart.sku.ilike(f"%{keyword}%"))
            | (SparePart.name.ilike(f"%{keyword}%"))
        )
    return q.order_by(SparePart.id.desc()).offset(skip).limit(limit).all()


def create_part(db: Session, obj_in: SparePartCreate) -> SparePart:
    if get_part_by_sku(db, obj_in.sku):
        raise HTTPException(status_code=400, detail="备件编号已存在")
    obj = SparePart(**obj_in.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    # 初始库存记一笔 IN
    if obj.current_stock > 0:
        _record_movement(db, obj, "IN", obj.current_stock, ref_type="INIT", ref_id=obj.id, operator_id=None, remark="期初")
    return obj


def update_part(db: Session, db_obj: SparePart, obj_in: SparePartUpdate) -> SparePart:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(db_obj, k, v)
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_part(db: Session, part_id: int):
    obj = get_part(db, part_id)
    if not obj:
        raise HTTPException(status_code=404, detail="备件不存在")
    db.delete(obj)
    db.commit()


def _record_movement(
    db: Session, part: SparePart, movement_type: str, qty: int,
    ref_type: Optional[str] = None, ref_id: Optional[int] = None,
    operator_id: Optional[int] = None, remark: Optional[str] = None,
) -> SparePartMovement:
    before = part.current_stock or 0
    if movement_type == "IN":
        after = before + qty
    elif movement_type == "OUT":
        after = before - qty
        if after < 0:
            raise HTTPException(status_code=400, detail=f"库存不足: 当前 {before}, 出库 {qty}")
    elif movement_type == "ADJUST":
        after = qty  # 调整为指定值
        qty = abs(after - before)
    else:
        raise HTTPException(status_code=400, detail="未知 movement_type")

    part.current_stock = after
    mv = SparePartMovement(
        spare_part_id=part.id,
        movement_type=movement_type,
        qty=qty,
        before_stock=before,
        after_stock=after,
        ref_type=ref_type,
        ref_id=ref_id,
        operator_id=operator_id,
        remark=remark,
    )
    db.add(mv)
    db.flush()
    return mv


def move_stock(
    db: Session, part_id: int, obj_in: StockMovement, operator_id: Optional[int] = None
) -> SparePartMovement:
    part = get_part(db, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="备件不存在")
    mv = _record_movement(
        db, part, obj_in.movement_type, obj_in.qty,
        ref_type="MANUAL", operator_id=operator_id, remark=obj_in.remark,
    )
    db.commit()
    db.refresh(mv)
    return mv


def list_movements(db: Session, part_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    q = db.query(SparePartMovement)
    if part_id:
        q = q.filter(SparePartMovement.spare_part_id == part_id)
    return q.order_by(SparePartMovement.id.desc()).offset(skip).limit(limit).all()


def get_stock_summary(db: Session) -> dict:
    """计算备件库存概览统计（不依赖 Python 循环，尽量走 SQL 聚合）。"""
    from sqlalchemy import func as sa_func
    # 基础统计
    total_skus = db.query(sa_func.count(SparePart.id)).scalar() or 0
    total_qty = db.query(sa_func.coalesce(sa_func.sum(SparePart.current_stock), 0)).scalar() or 0
    total_value = db.query(
        sa_func.coalesce(sa_func.sum(SparePart.current_stock * SparePart.unit_price), 0.0)
    ).scalar() or 0.0
    low_stock_count = (
        db.query(sa_func.count(SparePart.id))
        .filter(SparePart.current_stock <= SparePart.safety_stock)
        .scalar() or 0
    )
    out_of_stock_count = (
        db.query(sa_func.count(SparePart.id))
        .filter(SparePart.current_stock == 0)
        .scalar() or 0
    )
    return {
        "total_skus": int(total_skus),
        "total_qty": int(total_qty),
        "total_value": float(total_value),
        "low_stock_count": int(low_stock_count),
        "out_of_stock_count": int(out_of_stock_count),
    }


def list_all_movements(
    db: Session,
    keyword: Optional[str] = None,
    movement_type: Optional[str] = None,
    ref_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
):
    """全局出入库流水查询（支持按备件关键字 / 类型 / 来源过滤，并关联备件信息）。"""
    from sqlalchemy.orm import joinedload
    q = db.query(SparePartMovement).options(joinedload(SparePartMovement.spare_part))
    if movement_type:
        q = q.filter(SparePartMovement.movement_type == movement_type)
    if ref_type:
        q = q.filter(SparePartMovement.ref_type == ref_type)
    if keyword:
        # 子查询：按 sku/name 匹配的备件 id 集合
        sub = (
            db.query(SparePart.id)
            .filter(
                (SparePart.sku.ilike(f"%{keyword}%"))
                | (SparePart.name.ilike(f"%{keyword}%"))
            )
            .subquery()
        )
        q = q.filter(SparePartMovement.spare_part_id.in_(sub))
    return q.order_by(SparePartMovement.id.desc()).offset(skip).limit(limit).all()


# ----- 工单领用备件（内部接口, 由 work_order_service 调用）-----

def consume_for_work_order(
    db: Session, work_order_id: int, spare_part_id: int, qty: int,
    operator_id: Optional[int] = None, remark: Optional[str] = None,
) -> tuple:
    """返回 (usage, movement)"""
    from app.models import SparePartUsage
    part = get_part(db, spare_part_id)
    if not part:
        raise HTTPException(status_code=404, detail="备件不存在")
    mv = _record_movement(
        db, part, "OUT", qty,
        ref_type="WORK_ORDER", ref_id=work_order_id,
        operator_id=operator_id, remark=remark or f"工单 #{work_order_id} 领用",
    )
    usage = SparePartUsage(
        work_order_id=work_order_id,
        spare_part_id=spare_part_id,
        qty=qty,
        movement_id=mv.id,
        remark=remark,
    )
    db.add(usage)
    db.flush()
    return usage, mv


# ----- 设备-备件关联（易损件清单）-----

def list_equipment_parts(db: Session, equipment_id: int) -> List[EquipmentSparePart]:
    return (
        db.query(EquipmentSparePart)
        .filter(EquipmentSparePart.equipment_id == equipment_id)
        .all()
    )


def add_equipment_part(db: Session, equipment_id: int, obj_in: EquipmentSparePartCreate) -> EquipmentSparePart:
    if not get_part(db, obj_in.spare_part_id):
        raise HTTPException(status_code=404, detail="备件不存在")
    existing = (
        db.query(EquipmentSparePart)
        .filter(
            EquipmentSparePart.equipment_id == equipment_id,
            EquipmentSparePart.spare_part_id == obj_in.spare_part_id,
        )
        .first()
    )
    if existing:
        existing.qty_per = obj_in.qty_per
        existing.remark = obj_in.remark
        db.commit()
        db.refresh(existing)
        return existing
    obj = EquipmentSparePart(equipment_id=equipment_id, **obj_in.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def remove_equipment_part(db: Session, equipment_id: int, spare_part_id: int):
    obj = (
        db.query(EquipmentSparePart)
        .filter(
            EquipmentSparePart.equipment_id == equipment_id,
            EquipmentSparePart.spare_part_id == spare_part_id,
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="未找到关联")
    db.delete(obj)
    db.commit()
