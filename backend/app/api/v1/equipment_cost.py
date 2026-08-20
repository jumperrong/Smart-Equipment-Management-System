from datetime import datetime
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import EquipmentCost, Equipment
from app.schemas import EquipmentCostCreate, EquipmentCostOut, EquipmentCostUpdate
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/equipment-costs", tags=["设备成本LCC"])


def _user_display_name(user) -> str:
    return user.full_name or user.username


@router.get("", response_model=list[EquipmentCostOut])
def list_costs(
    equipment_id: Optional[int] = None,
    cost_type: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """成本记录列表，支持 equipment_id / cost_type / 时间范围过滤。"""
    q = db.query(EquipmentCost)
    if equipment_id is not None:
        q = q.filter(EquipmentCost.equipment_id == equipment_id)
    if cost_type:
        q = q.filter(EquipmentCost.cost_type == cost_type)
    if start:
        q = q.filter(EquipmentCost.cost_date >= start)
    if end:
        q = q.filter(EquipmentCost.cost_date <= end)
    q = q.order_by(EquipmentCost.cost_date.desc())
    return q.offset(skip).limit(limit).all()


@router.post("", response_model=EquipmentCostOut, dependencies=[Depends(require_permission("equipment_cost.write"))])
def create_cost(
    obj_in: EquipmentCostCreate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    data = obj_in.model_dump()
    # cost_date 留空则由模型默认值在 commit 后填充，这里显式设置便于立即返回
    if data.get("cost_date") is None:
        data["cost_date"] = datetime.utcnow()
    obj = EquipmentCost(
        **data,
        recorded_by_id=current_user.id,
        recorded_by_name=_user_display_name(current_user),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/summary")
def overall_summary(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """全设备成本汇总：按类型汇总 + Top10 高成本设备。"""
    q = db.query(EquipmentCost)
    if start:
        q = q.filter(EquipmentCost.cost_date >= start)
    if end:
        q = q.filter(EquipmentCost.cost_date <= end)

    # 按类型汇总
    by_type_rows = (
        db.query(
            EquipmentCost.cost_type,
            func.sum(EquipmentCost.amount).label("total"),
            func.count(EquipmentCost.id).label("count"),
        )
    )
    if start:
        by_type_rows = by_type_rows.filter(EquipmentCost.cost_date >= start)
    if end:
        by_type_rows = by_type_rows.filter(EquipmentCost.cost_date <= end)
    by_type_rows = by_type_rows.group_by(EquipmentCost.cost_type).all()

    type_summary = [
        {"cost_type": r.cost_type, "total": float(r.total or 0), "count": int(r.count or 0)}
        for r in by_type_rows
    ]
    total_cost = float(sum((r.total or 0) for r in by_type_rows))

    # Top10 高成本设备
    top_rows = (
        db.query(
            EquipmentCost.equipment_id,
            func.sum(EquipmentCost.amount).label("total"),
        )
    )
    if start:
        top_rows = top_rows.filter(EquipmentCost.cost_date >= start)
    if end:
        top_rows = top_rows.filter(EquipmentCost.cost_date <= end)
    top_rows = (
        top_rows.group_by(EquipmentCost.equipment_id)
        .order_by(func.sum(EquipmentCost.amount).desc())
        .limit(10)
        .all()
    )
    top_equipment_ids = [r.equipment_id for r in top_rows]
    name_map = {}
    if top_equipment_ids:
        eqs = db.query(Equipment).filter(Equipment.id.in_(top_equipment_ids)).all()
        name_map = {e.id: e.name for e in eqs}
    top_equipments = [
        {
            "equipment_id": r.equipment_id,
            "equipment_name": name_map.get(r.equipment_id),
            "total": float(r.total or 0),
        }
        for r in top_rows
    ]

    return {
        "total_cost": total_cost,
        "by_type": type_summary,
        "top_equipments": top_equipments,
    }


@router.get("/equipment/{equipment_id}/summary")
def equipment_summary(
    equipment_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """单设备 LCC 汇总：按类型汇总 + 总成本 + 年度趋势。"""
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")

    base = db.query(EquipmentCost).filter(EquipmentCost.equipment_id == equipment_id)
    if start:
        base = base.filter(EquipmentCost.cost_date >= start)
    if end:
        base = base.filter(EquipmentCost.cost_date <= end)

    # 按类型汇总
    by_type_rows = (
        db.query(
            EquipmentCost.cost_type,
            func.sum(EquipmentCost.amount).label("total"),
            func.count(EquipmentCost.id).label("count"),
        )
        .filter(EquipmentCost.equipment_id == equipment_id)
    )
    if start:
        by_type_rows = by_type_rows.filter(EquipmentCost.cost_date >= start)
    if end:
        by_type_rows = by_type_rows.filter(EquipmentCost.cost_date <= end)
    by_type_rows = by_type_rows.group_by(EquipmentCost.cost_type).all()

    type_summary = [
        {"cost_type": r.cost_type, "total": float(r.total or 0), "count": int(r.count or 0)}
        for r in by_type_rows
    ]
    total_cost = float(sum((r.total or 0) for r in by_type_rows))

    # 年度趋势
    yearly_rows = (
        db.query(
            extract("year", EquipmentCost.cost_date).label("year"),
            func.sum(EquipmentCost.amount).label("total"),
        )
        .filter(EquipmentCost.equipment_id == equipment_id)
    )
    if start:
        yearly_rows = yearly_rows.filter(EquipmentCost.cost_date >= start)
    if end:
        yearly_rows = yearly_rows.filter(EquipmentCost.cost_date <= end)
    yearly_rows = (
        yearly_rows.group_by(extract("year", EquipmentCost.cost_date))
        .order_by(extract("year", EquipmentCost.cost_date).asc())
        .all()
    )
    yearly_trend = [
        {"year": int(r.year), "total": float(r.total or 0)}
        for r in yearly_rows
    ]

    return {
        "equipment_id": equipment_id,
        "equipment_name": eq.name,
        "total_cost": total_cost,
        "by_type": type_summary,
        "yearly_trend": yearly_trend,
    }


@router.put("/{cost_id}", response_model=EquipmentCostOut, dependencies=[Depends(require_permission("equipment_cost.write"))])
def update_cost(
    cost_id: int, obj_in: EquipmentCostUpdate,
    db: Session = Depends(get_db),
):
    obj = db.query(EquipmentCost).filter(EquipmentCost.id == cost_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="成本记录不存在")
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{cost_id}", dependencies=[Depends(require_permission("equipment_cost.delete"))])
def delete_cost(cost_id: int, db: Session = Depends(get_db)):
    obj = db.query(EquipmentCost).filter(EquipmentCost.id == cost_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="成本记录不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True}
