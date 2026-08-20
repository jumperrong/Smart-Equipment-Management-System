from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import DispatchCreate, DispatchUpdate, DispatchOut
from app.services.dispatch_service import (
    list_dispatches, get_dispatch, create_dispatch, update_dispatch, delete_dispatch
)
from app.models import Equipment, User, ProcessSection, FormTemplate

router = APIRouter(prefix="/dispatches", tags=["派工"])


def _to_out(db: Session, d) -> DispatchOut:
    """ORM → DispatchOut，填充展示辅助字段。"""
    out = DispatchOut.model_validate(d)
    if d.equipment_id:
        eq = db.query(Equipment).filter(Equipment.id == d.equipment_id).first()
        out.equipment_name = eq.name if eq else None
    if d.assigned_operator_id:
        op = db.query(User).filter(User.id == d.assigned_operator_id).first()
        out.operator_name = op.username if op else None
    if d.labor_reports:
        out.labor_reports_count = len(d.labor_reports)
    if d.process_section_id:
        ps = db.query(ProcessSection).filter(ProcessSection.id == d.process_section_id).first()
        out.process_section_name = ps.name if ps else None
    if d.form_template_id:
        tpl = db.query(FormTemplate).filter(FormTemplate.id == d.form_template_id).first()
        out.form_template_name = tpl.name if tpl else None
    return out


@router.get("", response_model=list[DispatchOut])
def list_dispatches_api(
    mo_id: int | None = Query(None),
    equipment_id: int | None = Query(None),
    status: str | None = Query(None),
    operator_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    items = list_dispatches(
        db,
        mo_id=mo_id,
        equipment_id=equipment_id,
        status=status,
        operator_id=operator_id,
        skip=skip,
        limit=limit,
    )
    return [_to_out(db, d) for d in items]


@router.get("/{dispatch_id}", response_model=DispatchOut)
def get_dispatch_api(dispatch_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    d = get_dispatch(db, dispatch_id)
    return _to_out(db, d)


@router.post("", response_model=DispatchOut, dependencies=[Depends(require_permission("production.dispatch_assign"))])
def create_dispatch_api(obj_in: DispatchCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    d = create_dispatch(db, obj_in, cu.id, cu.username)
    return _to_out(db, d)


@router.put("/{dispatch_id}", response_model=DispatchOut, dependencies=[Depends(require_permission("production.dispatch_assign"))])
def update_dispatch_api(dispatch_id: int, obj_in: DispatchUpdate, db: Session = Depends(get_db)):
    d = get_dispatch(db, dispatch_id)
    updated = update_dispatch(db, d, obj_in)
    return _to_out(db, updated)


@router.delete("/{dispatch_id}", dependencies=[Depends(require_permission("production.dispatch_assign"))])
def delete_dispatch_api(dispatch_id: int, db: Session = Depends(get_db)):
    d = get_dispatch(db, dispatch_id)
    delete_dispatch(db, d)
    return {"detail": "已删除"}
