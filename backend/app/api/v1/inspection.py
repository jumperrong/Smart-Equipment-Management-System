from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import UserRole
from app.schemas import (
    InspectionTemplateCreate, InspectionTemplateUpdate, InspectionTemplateOut,
    InspectionRecordCreate, InspectionRecordOut,
)
from app.services import inspection_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/inspections", tags=["点检巡检"])

# 模板
@router.get("/templates", response_model=list[InspectionTemplateOut])
def list_templates(
    equipment_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return inspection_service.list_templates(db, equipment_id=equipment_id, skip=skip, limit=limit)


@router.post("/templates", response_model=InspectionTemplateOut, dependencies=[Depends(require_permission("inspection.template_write"))])
def create_template(obj_in: InspectionTemplateCreate, db: Session = Depends(get_db)):
    return inspection_service.create_template(db, obj_in)


@router.put("/templates/{tpl_id}", response_model=InspectionTemplateOut, dependencies=[Depends(require_permission("inspection.template_write"))])
def update_template(tpl_id: int, obj_in: InspectionTemplateUpdate, db: Session = Depends(get_db)):
    tpl = inspection_service.get_template(db, tpl_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return inspection_service.update_template(db, tpl, obj_in)


@router.delete("/templates/{tpl_id}", dependencies=[Depends(require_permission("inspection.template_delete"))])
def delete_template(tpl_id: int, db: Session = Depends(get_db)):
    inspection_service.delete_template(db, tpl_id)
    return {"ok": True}


# 记录
@router.get("/records", response_model=list[InspectionRecordOut])
def list_records(
    template_id: Optional[int] = None, equipment_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return inspection_service.list_records(db, template_id=template_id, equipment_id=equipment_id, skip=skip, limit=limit)


@router.get("/records/{record_id}", response_model=InspectionRecordOut)
def get_record(record_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rec = inspection_service.get_record(db, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    return rec


@router.post("/records", response_model=InspectionRecordOut, dependencies=[Depends(require_permission("inspection.record_create"))])
def create_record(
    obj_in: InspectionRecordCreate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return inspection_service.create_record(db, obj_in, current_user)
