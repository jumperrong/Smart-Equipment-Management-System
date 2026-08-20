"""首件检验 FAI API：CRUD + 提交 + QA 签核。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import FAICreate, FAIUpdate, FAIReview, FAIOut
from app.services.fai_service import (
    list_fais, get_fai, get_fai_by_dispatch, create_fai, update_fai,
    submit_fai, review_fai, delete_fai,
)
from app.models import ProductionOrder, Product, Equipment

router = APIRouter(prefix="/fais", tags=["首件检验 FAI"])


def _to_out(db: Session, fai) -> FAIOut:
    out = FAIOut.model_validate(fai)
    if fai.mo_id:
        mo = db.query(ProductionOrder).filter(ProductionOrder.id == fai.mo_id).first()
        if mo:
            out.mo_no = mo.mo_no
    if fai.product_id:
        p = db.query(Product).filter(Product.id == fai.product_id).first()
        if p:
            out.product_code = p.code
            out.product_name = p.name
    if fai.equipment_id:
        eq = db.query(Equipment).filter(Equipment.id == fai.equipment_id).first()
        if eq:
            out.equipment_name = eq.name
    return out


@router.get("", response_model=list[FAIOut], dependencies=[Depends(require_permission("production.fai_view"))])
def list_fais_api(
    status: str | None = Query(None),
    dispatch_id: int | None = Query(None),
    mo_id: int | None = Query(None),
    product_id: int | None = Query(None),
    reviewer_id: int | None = Query(None),
    keyword: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    items = list_fais(
        db,
        status=status,
        dispatch_id=dispatch_id,
        mo_id=mo_id,
        product_id=product_id,
        reviewer_id=reviewer_id,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return [_to_out(db, x) for x in items]


@router.get(
    "/by-dispatch/{dispatch_id}",
    response_model=Optional[FAIOut],
    dependencies=[Depends(require_permission("production.fai_view"))],
)
def get_fai_by_dispatch_api(dispatch_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    fai = get_fai_by_dispatch(db, dispatch_id)
    return _to_out(db, fai) if fai else None


@router.get("/{fai_id}", response_model=FAIOut, dependencies=[Depends(require_permission("production.fai_view"))])
def get_fai_api(fai_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return _to_out(db, get_fai(db, fai_id))


@router.post("", response_model=FAIOut, dependencies=[Depends(require_permission("production.fai_manage"))])
def create_fai_api(obj_in: FAICreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return _to_out(db, create_fai(db, obj_in, cu.id, cu.username))


@router.put("/{fai_id}", response_model=FAIOut, dependencies=[Depends(require_permission("production.fai_manage"))])
def update_fai_api(fai_id: int, obj_in: FAIUpdate, db: Session = Depends(get_db)):
    fai = get_fai(db, fai_id)
    return _to_out(db, update_fai(db, fai, obj_in))


@router.post("/{fai_id}/submit", response_model=FAIOut, dependencies=[Depends(require_permission("production.fai_manage"))])
def submit_fai_api(fai_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    """提交 FAI：DRAFT -> PENDING_QA。"""
    fai = get_fai(db, fai_id)
    return _to_out(db, submit_fai(db, fai, cu.id, cu.username))


@router.post("/{fai_id}/review", response_model=FAIOut, dependencies=[Depends(require_permission("production.fai_manage"))])
def review_fai_api(
    fai_id: int,
    obj_in: FAIReview,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """QA 签核 FAI：APPROVED / REJECTED。"""
    fai = get_fai(db, fai_id)
    return _to_out(db, review_fai(db, fai, obj_in, cu.id, cu.username))


@router.delete("/{fai_id}", dependencies=[Depends(require_permission("production.fai_manage"))])
def delete_fai_api(fai_id: int, db: Session = Depends(get_db)):
    fai = get_fai(db, fai_id)
    delete_fai(db, fai)
    return {"detail": "已删除"}
