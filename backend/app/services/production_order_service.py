from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import ProductionOrder, ProductionOrderStatus, MOSourceType, Product, Routing, RoutingStatus
from app.schemas import ProductionOrderCreate, ProductionOrderUpdate


VALID_MO_TRANSITIONS = {
    ("DRAFT", "RELEASED"), ("DRAFT", "CANCELLED"),
    ("RELEASED", "IN_PROGRESS"), ("RELEASED", "CANCELLED"),
    ("IN_PROGRESS", "COMPLETED"),
    ("COMPLETED", "CLOSED"), ("COMPLETED", "IN_PROGRESS"),
}


def _gen_mo_no(db: Session) -> str:
    now = datetime.utcnow()
    prefix = f"MO-{now.strftime('%Y%m%d')}-"
    count = db.query(ProductionOrder).filter(ProductionOrder.mo_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def list_production_orders(db: Session, status: str | None = None, product_id: int | None = None, skip: int = 0, limit: int = 50):
    q = db.query(ProductionOrder)
    if status:
        q = q.filter(ProductionOrder.status == status)
    if product_id:
        q = q.filter(ProductionOrder.product_id == product_id)
    return q.order_by(ProductionOrder.id.desc()).offset(skip).limit(limit).all()


def get_production_order(db: Session, mo_id: int) -> ProductionOrder:
    mo = db.query(ProductionOrder).filter(ProductionOrder.id == mo_id).first()
    if not mo:
        raise HTTPException(404, "生产订单不存在")
    return mo


def create_production_order(db: Session, obj_in: ProductionOrderCreate, user_id: int, user_name: str) -> ProductionOrder:
    product = db.query(Product).filter(Product.id == obj_in.product_id).first()
    if not product:
        raise HTTPException(404, "产品不存在")
    if obj_in.routing_id:
        routing = db.query(Routing).filter(Routing.id == obj_in.routing_id).first()
        if not routing:
            raise HTTPException(404, "工序路由不存在")
        if routing.status != RoutingStatus.EFFECTIVE.value:
            raise HTTPException(400, "工序路由未生效，不可用于生产订单")
    mo = ProductionOrder(
        mo_no=_gen_mo_no(db),
        product_id=obj_in.product_id,
        routing_id=obj_in.routing_id,
        batch_no=obj_in.batch_no,
        priority=obj_in.priority,
        status=ProductionOrderStatus.DRAFT.value,
        source_type=obj_in.source_type,
        parent_mo_id=obj_in.parent_mo_id,
        customer_po=obj_in.customer_po,
        plan_qty=obj_in.plan_qty,
        planned_start=obj_in.planned_start,
        planned_end=obj_in.planned_end,
        created_by_id=user_id,
        created_by_name=user_name,
        remark=obj_in.remark,
    )
    db.add(mo)
    db.commit()
    db.refresh(mo)
    return mo


def update_production_order(db: Session, mo: ProductionOrder, obj_in: ProductionOrderUpdate) -> ProductionOrder:
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    new_status = data.get("status")
    if new_status and mo.status and mo.status != new_status:
        old_status = mo.status if isinstance(mo.status, str) else mo.status.value
        if (old_status, new_status) not in VALID_MO_TRANSITIONS:
            raise HTTPException(400, f"生产订单状态不允许从 {old_status} 跳转到 {new_status}")
        if new_status == ProductionOrderStatus.RELEASED.value:
            data["released_by_id"] = mo.created_by_id
            data["released_by_name"] = mo.created_by_name
        if new_status == ProductionOrderStatus.IN_PROGRESS.value and not mo.actual_start:
            data["actual_start"] = datetime.utcnow()
        if new_status == ProductionOrderStatus.COMPLETED.value and not mo.actual_end:
            data["actual_end"] = datetime.utcnow()
        if new_status == ProductionOrderStatus.CLOSED.value:
            data["closed_by_id"] = mo.created_by_id
            data["closed_by_name"] = mo.created_by_name
    for k, v in data.items():
        setattr(mo, k, v)
    db.commit()
    db.refresh(mo)
    return mo


def delete_production_order(db: Session, mo: ProductionOrder):
    if mo.status not in (ProductionOrderStatus.DRAFT.value, ProductionOrderStatus.CANCELLED.value):
        raise HTTPException(400, "只有草稿或已取消的订单可删除")
    db.delete(mo)
    db.commit()
