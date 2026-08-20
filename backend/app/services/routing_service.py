from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Routing, RoutingStep, RoutingStatus, Product
from app.schemas import RoutingCreate, RoutingUpdate, RoutingStepCreate


def list_routings(db: Session, product_id: int | None = None, status: str | None = None, skip: int = 0, limit: int = 50):
    q = db.query(Routing)
    if product_id:
        q = q.filter(Routing.product_id == product_id)
    if status:
        q = q.filter(Routing.status == status)
    return q.order_by(Routing.id.desc()).offset(skip).limit(limit).all()


def get_routing(db: Session, routing_id: int) -> Routing:
    r = db.query(Routing).filter(Routing.id == routing_id).first()
    if not r:
        raise HTTPException(404, "工序路由不存在")
    return r


def create_routing(db: Session, obj_in: RoutingCreate, user_id: int, user_name: str) -> Routing:
    product = db.query(Product).filter(Product.id == obj_in.product_id).first()
    if not product:
        raise HTTPException(404, "产品不存在")
    r = Routing(
        product_id=obj_in.product_id,
        version=obj_in.version,
        status=RoutingStatus.DRAFT.value,
        change_reason=obj_in.change_reason,
        remark=obj_in.remark,
        created_by_id=user_id,
        created_by_name=user_name,
    )
    db.add(r)
    db.flush()
    for step_in in obj_in.steps:
        step = RoutingStep(
            routing_id=r.id,
            seq=step_in.seq,
            step_name=step_in.step_name,
            process_section_id=step_in.process_section_id,
            standard_cycle_min=step_in.standard_cycle_min,
            theoretical_uph=step_in.theoretical_uph,
            process_params_schema=step_in.process_params_schema,
            acceptance_criteria=step_in.acceptance_criteria,
            sop_doc_id=step_in.sop_doc_id,
            param_form_template_id=step_in.param_form_template_id,
            equipment_group=step_in.equipment_group,
            required_skill_level=step_in.required_skill_level,
            remark=step_in.remark,
        )
        db.add(step)
    db.commit()
    db.refresh(r)
    return r


def update_routing(db: Session, routing: Routing, obj_in: RoutingUpdate) -> Routing:
    if routing.status == RoutingStatus.OBSOLETE.value:
        raise HTTPException(400, "作废的路由不可修改")
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    steps_data = data.pop("steps", None)
    for k, v in data.items():
        setattr(routing, k, v)
    if steps_data is not None:
        # 删除旧步骤
        db.query(RoutingStep).filter(RoutingStep.routing_id == routing.id).delete()
        for step_in in steps_data:
            step = RoutingStep(routing_id=routing.id, **step_in)
            db.add(step)
    db.commit()
    db.refresh(routing)
    return routing


def release_routing(db: Session, routing: Routing) -> Routing:
    if routing.status != RoutingStatus.DRAFT.value:
        raise HTTPException(400, "只有草稿状态的路由才能生效")
    routing.status = RoutingStatus.EFFECTIVE.value
    routing.effective_date = datetime.utcnow()
    routing.next_review_date = datetime(routing.effective_date.year + 1, routing.effective_date.month, routing.effective_date.day) if routing.effective_date else None
    # 同产品其他生效版本自动作废
    db.query(Routing).filter(
        Routing.product_id == routing.product_id,
        Routing.status == RoutingStatus.EFFECTIVE.value,
        Routing.id != routing.id,
    ).update({"status": RoutingStatus.OBSOLETE.value})
    db.commit()
    db.refresh(routing)
    return routing


def delete_routing(db: Session, routing: Routing):
    if routing.status == RoutingStatus.EFFECTIVE.value:
        raise HTTPException(400, "生效中的路由不可删除，请先作废")
    db.delete(routing)
    db.commit()
