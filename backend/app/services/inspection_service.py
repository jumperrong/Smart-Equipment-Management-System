from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    InspectionTemplate, InspectionItem, InspectionRecord, InspectionResult, User,
)
from app.schemas import (
    InspectionTemplateCreate, InspectionTemplateUpdate, InspectionTemplateOut,
    InspectionRecordCreate, InspectionRecordOut,
)


def get_template(db: Session, tpl_id: int) -> Optional[InspectionTemplate]:
    return db.query(InspectionTemplate).filter(InspectionTemplate.id == tpl_id).first()


def list_templates(db: Session, equipment_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    q = db.query(InspectionTemplate)
    if equipment_id:
        q = q.filter(InspectionTemplate.equipment_id == equipment_id)
    return q.order_by(InspectionTemplate.id.desc()).offset(skip).limit(limit).all()


def create_template(db: Session, obj_in: InspectionTemplateCreate) -> InspectionTemplate:
    items_data = obj_in.model_dump().pop("items", [])
    tpl = InspectionTemplate(**{k: v for k, v in obj_in.model_dump().items() if k != "items"})
    db.add(tpl)
    db.flush()
    for it in items_data:
        db.add(InspectionItem(template_id=tpl.id, **it))
    db.commit()
    db.refresh(tpl)
    return tpl


def update_template(db: Session, tpl: InspectionTemplate, obj_in: InspectionTemplateUpdate) -> InspectionTemplate:
    data = obj_in.model_dump(exclude_unset=True)
    items_data = data.pop("items", None)
    for k, v in data.items():
        setattr(tpl, k, v)
    tpl.updated_at = datetime.utcnow()
    if items_data is not None:
        # 整体替换 items
        db.query(InspectionItem).filter(InspectionItem.template_id == tpl.id).delete()
        for it in items_data:
            db.add(InspectionItem(template_id=tpl.id, **it))
    db.commit()
    db.refresh(tpl)
    return tpl


def delete_template(db: Session, tpl_id: int):
    tpl = get_template(db, tpl_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    db.delete(tpl)
    db.commit()


def list_records(
    db: Session, template_id: Optional[int] = None, equipment_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(InspectionRecord)
    if template_id:
        q = q.filter(InspectionRecord.template_id == template_id)
    if equipment_id:
        q = q.filter(InspectionRecord.equipment_id == equipment_id)
    return q.order_by(InspectionRecord.id.desc()).offset(skip).limit(limit).all()


def get_record(db: Session, record_id: int) -> Optional[InspectionRecord]:
    return db.query(InspectionRecord).filter(InspectionRecord.id == record_id).first()


def create_record(
    db: Session, obj_in: InspectionRecordCreate, inspector: User
) -> InspectionRecord:
    tpl = get_template(db, obj_in.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="点检模板不存在")

    overall = "OK"
    for r in obj_in.results:
        if r.result == "NG":
            overall = "NG"
            break

    rec = InspectionRecord(
        template_id=obj_in.template_id,
        equipment_id=obj_in.equipment_id or tpl.equipment_id,
        shift=obj_in.shift,
        inspect_time=obj_in.inspect_time or datetime.utcnow(),
        inspector_id=inspector.id,
        overall_result=overall,
        remark=obj_in.remark,
    )
    db.add(rec)
    db.flush()
    for r in obj_in.results:
        db.add(InspectionResult(
            record_id=rec.id,
            item_id=r.item_id,
            item_name=r.item_name,
            result=r.result,
            value=r.value,
            remark=r.remark,
        ))
    db.commit()
    db.refresh(rec)
    return rec
