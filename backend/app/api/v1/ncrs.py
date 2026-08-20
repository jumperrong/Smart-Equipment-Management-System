"""不合格品报告 NCR API：CRUD + 评审 + 结案。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import NCRCreate, NCRUpdate, NCRReview, NCROut
from app.services.ncr_service import (
    list_ncrs, get_ncr, create_ncr, update_ncr, review_ncr, close_ncr, delete_ncr,
)
from app.models import Lot, ProductionOrder, Product

router = APIRouter(prefix="/ncrs", tags=["不合格品NCR"])


def _to_out(db: Session, ncr) -> NCROut:
    out = NCROut.model_validate(ncr)
    if ncr.lot_id:
        lot = db.query(Lot).filter(Lot.id == ncr.lot_id).first()
        if lot:
            out.lot_no = lot.lot_no
    if ncr.mo_id:
        mo = db.query(ProductionOrder).filter(ProductionOrder.id == ncr.mo_id).first()
        if mo:
            out.mo_no = mo.mo_no
    if ncr.product_id:
        p = db.query(Product).filter(Product.id == ncr.product_id).first()
        if p:
            out.product_code = p.code
            out.product_name = p.name
    return out


@router.get("", response_model=list[NCROut])
def list_ncrs_api(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    lot_id: int | None = Query(None),
    mo_id: int | None = Query(None),
    dispatch_id: int | None = Query(None),
    labor_report_id: int | None = Query(None),
    keyword: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    items = list_ncrs(
        db,
        status=status,
        severity=severity,
        lot_id=lot_id,
        mo_id=mo_id,
        dispatch_id=dispatch_id,
        labor_report_id=labor_report_id,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return [_to_out(db, x) for x in items]


@router.get("/{ncr_id}", response_model=NCROut)
def get_ncr_api(ncr_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return _to_out(db, get_ncr(db, ncr_id))


@router.post("", response_model=NCROut, dependencies=[Depends(require_permission("production.ncr_manage"))])
def create_ncr_api(obj_in: NCRCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return _to_out(db, create_ncr(db, obj_in, cu.id, cu.username))


@router.put("/{ncr_id}", response_model=NCROut, dependencies=[Depends(require_permission("production.ncr_manage"))])
def update_ncr_api(ncr_id: int, obj_in: NCRUpdate, db: Session = Depends(get_db)):
    ncr = get_ncr(db, ncr_id)
    return _to_out(db, update_ncr(db, ncr, obj_in))


@router.post("/{ncr_id}/review", response_model=NCROut, dependencies=[Depends(require_permission("production.ncr_manage"))])
def review_ncr_api(
    ncr_id: int,
    obj_in: NCRReview,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """评审 NCR：写入 disposition / root_cause / corrective_action。"""
    ncr = get_ncr(db, ncr_id)
    return _to_out(db, review_ncr(db, ncr, obj_in, cu.id, cu.username))


@router.post("/{ncr_id}/close", response_model=NCROut, dependencies=[Depends(require_permission("production.ncr_manage"))])
def close_ncr_api(ncr_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    """结案 NCR。"""
    ncr = get_ncr(db, ncr_id)
    return _to_out(db, close_ncr(db, ncr, cu.id, cu.username))


@router.delete("/{ncr_id}", dependencies=[Depends(require_permission("production.ncr_manage"))])
def delete_ncr_api(ncr_id: int, db: Session = Depends(get_db)):
    ncr = get_ncr(db, ncr_id)
    delete_ncr(db, ncr)
    return {"detail": "已删除"}
