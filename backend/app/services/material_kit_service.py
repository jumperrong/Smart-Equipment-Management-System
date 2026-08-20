"""派工物料齐套（Kit Check）服务。

场景：派工开工前由计划员/仓管录入或导入物料需求与齐套状态；
防呆：dispatch_id 下任一 MaterialKitItem.is_kitted=false 视为未齐套。
"""
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import MaterialKitItem, Dispatch
from app.schemas import (
    MaterialKitItemCreate,
    MaterialKitItemUpdate,
    KitCheckResult,
)


def list_kit_items(
    db: Session,
    dispatch_id: int | None = None,
    is_kitted: bool | None = None,
    keyword: str | None = None,
    skip: int = 0,
    limit: int = 200,
) -> list[MaterialKitItem]:
    q = db.query(MaterialKitItem)
    if dispatch_id is not None:
        q = q.filter(MaterialKitItem.dispatch_id == dispatch_id)
    if is_kitted is not None:
        q = q.filter(MaterialKitItem.is_kitted == is_kitted)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (MaterialKitItem.material_code.like(kw))
            | (MaterialKitItem.material_name.like(kw))
            | (MaterialKitItem.spec.like(kw))
        )
    return q.order_by(MaterialKitItem.id.asc()).offset(skip).limit(limit).all()


def get_kit_item(db: Session, item_id: int) -> MaterialKitItem:
    item = db.query(MaterialKitItem).filter(MaterialKitItem.id == item_id).first()
    if not item:
        raise HTTPException(404, f"物料齐套项 id={item_id} 不存在")
    return item


def _resolve_is_kitted(obj_in: MaterialKitItemCreate) -> bool:
    """未显式传入 is_kitted 时按 available >= required 自动判定。"""
    unset = obj_in.model_dump(exclude_unset=True)
    if "is_kitted" in unset:
        return unset["is_kitted"]
    return obj_in.available_qty >= obj_in.required_qty


def _shortage_qty(required_qty: float, available_qty: float) -> float:
    return max(0.0, required_qty - available_qty)


def _apply_checked(item: MaterialKitItem, is_kitted: bool, user_id, user_name) -> None:
    if is_kitted:
        item.checked_at = datetime.utcnow()
        item.checked_by_id = user_id
        item.checked_by_name = user_name
    else:
        item.checked_at = None
        item.checked_by_id = None
        item.checked_by_name = None


def create_kit_item(
    db: Session,
    obj_in: MaterialKitItemCreate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> MaterialKitItem:
    # 单条创建必须在 body 中提供 dispatch_id（bulk 接口由路径参数提供）
    if obj_in.dispatch_id is None:
        raise HTTPException(400, "单条创建物料齐套项时 dispatch_id 必填（批量创建请用 /material-kits/bulk/{dispatch_id}）")
    # 校验派工存在
    d = db.query(Dispatch).filter(Dispatch.id == obj_in.dispatch_id).first()
    if not d:
        raise HTTPException(404, f"派工 id={obj_in.dispatch_id} 不存在")

    required_qty = obj_in.required_qty
    available_qty = obj_in.available_qty
    is_kitted = _resolve_is_kitted(obj_in)
    shortage_qty = _shortage_qty(required_qty, available_qty)

    item = MaterialKitItem(
        dispatch_id=obj_in.dispatch_id,
        material_code=obj_in.material_code,
        material_name=obj_in.material_name,
        spec=obj_in.spec,
        unit=obj_in.unit,
        required_qty=required_qty,
        available_qty=available_qty,
        is_kitted=is_kitted,
        shortage_qty=shortage_qty,
        location=obj_in.location,
        remark=obj_in.remark,
    )
    if is_kitted:
        _apply_checked(item, True, user_id, user_name)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_kit_items_bulk(
    db: Session,
    dispatch_id: int,
    items: list[MaterialKitItemCreate],
    user_id: int | None = None,
    user_name: str | None = None,
) -> list[MaterialKitItem]:
    # 校验派工存在
    d = db.query(Dispatch).filter(Dispatch.id == dispatch_id).first()
    if not d:
        raise HTTPException(404, f"派工 id={dispatch_id} 不存在")

    created: list[MaterialKitItem] = []
    for obj_in in items:
        required_qty = obj_in.required_qty
        available_qty = obj_in.available_qty
        is_kitted = _resolve_is_kitted(obj_in)
        shortage_qty = _shortage_qty(required_qty, available_qty)
        item = MaterialKitItem(
            dispatch_id=dispatch_id,
            material_code=obj_in.material_code,
            material_name=obj_in.material_name,
            spec=obj_in.spec,
            unit=obj_in.unit,
            required_qty=required_qty,
            available_qty=available_qty,
            is_kitted=is_kitted,
            shortage_qty=shortage_qty,
            location=obj_in.location,
            remark=obj_in.remark,
        )
        if is_kitted:
            _apply_checked(item, True, user_id, user_name)
        db.add(item)
        created.append(item)

    db.commit()
    for it in created:
        db.refresh(it)
    return created


def update_kit_item(
    db: Session,
    item: MaterialKitItem,
    obj_in: MaterialKitItemUpdate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> MaterialKitItem:
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    qty_changed = "required_qty" in data or "available_qty" in data
    is_kitted_changed = "is_kitted" in data

    for k, v in data.items():
        setattr(item, k, v)

    if qty_changed:
        item.shortage_qty = _shortage_qty(item.required_qty, item.available_qty)

    if is_kitted_changed:
        _apply_checked(item, bool(data["is_kitted"]), user_id, user_name)

    db.commit()
    db.refresh(item)
    return item


def check_kit(db: Session, dispatch_id: int) -> KitCheckResult:
    items = (
        db.query(MaterialKitItem)
        .filter(MaterialKitItem.dispatch_id == dispatch_id)
        .order_by(MaterialKitItem.id.asc())
        .all()
    )
    total_items = len(items)
    kitted_items = sum(1 for x in items if x.is_kitted)
    short_items = sum(1 for x in items if not x.is_kitted)
    all_kitted = short_items == 0 and total_items > 0
    shortage_summary = [
        {
            "material_code": x.material_code,
            "material_name": x.material_name,
            "required_qty": x.required_qty,
            "available_qty": x.available_qty,
            "shortage_qty": x.shortage_qty,
        }
        for x in items if not x.is_kitted
    ]
    return KitCheckResult(
        dispatch_id=dispatch_id,
        total_items=total_items,
        kitted_items=kitted_items,
        short_items=short_items,
        all_kitted=all_kitted,
        shortage_summary=shortage_summary,
    )


def mark_all_kitted(
    db: Session,
    dispatch_id: int,
    user_id: int | None = None,
    user_name: str | None = None,
) -> KitCheckResult:
    items = (
        db.query(MaterialKitItem)
        .filter(MaterialKitItem.dispatch_id == dispatch_id)
        .all()
    )
    now = datetime.utcnow()
    for x in items:
        x.is_kitted = True
        x.checked_at = now
        x.checked_by_id = user_id
        x.checked_by_name = user_name
    db.commit()
    return check_kit(db, dispatch_id)


def delete_kit_item(db: Session, item: MaterialKitItem) -> None:
    db.delete(item)
    db.commit()
