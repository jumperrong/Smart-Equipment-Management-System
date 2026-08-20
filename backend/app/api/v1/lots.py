"""批次追溯 API：批次 CRUD + 流转日志 + 谱系追溯。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import (
    LotCreate, LotUpdate, LotOut,
    LotTransactionCreate, LotTransactionOut,
    LotGenealogyCreate,
)
from app.services.lot_service import (
    list_lots, get_lot, create_lot, update_lot, delete_lot,
    add_transaction, list_transactions,
    link_genealogy, get_ancestors, get_descendants,
)
from app.models import Product, ProductionOrder

router = APIRouter(prefix="/lots", tags=["批次追溯"])


def _to_out(db: Session, lot) -> LotOut:
    out = LotOut.model_validate(lot)
    # 补展示字段
    if lot.product:
        out.product_code = lot.product.code
        out.product_name = lot.product.name
    if lot.production_order:
        out.mo_no = lot.production_order.mo_no
    # 谱系 ID
    parent_ids = [g.parent_lot_id for g in (lot.parents or [])]
    child_ids = [g.child_lot_id for g in (lot.children or [])]
    out.parent_lot_ids = parent_ids
    out.child_lot_ids = child_ids
    return out


@router.get("", response_model=list[LotOut])
def list_lots_api(
    product_id: int | None = Query(None),
    mo_id: int | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None, description="按批次号/供应商批次模糊搜索"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    items = list_lots(
        db,
        product_id=product_id,
        mo_id=mo_id,
        status=status,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return [_to_out(db, x) for x in items]


@router.get("/{lot_id}", response_model=LotOut)
def get_lot_api(lot_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return _to_out(db, get_lot(db, lot_id))


@router.post("", response_model=LotOut, dependencies=[Depends(require_permission("production.lot_manage"))])
def create_lot_api(obj_in: LotCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return _to_out(db, create_lot(db, obj_in, cu.id, cu.username))


@router.put("/{lot_id}", response_model=LotOut, dependencies=[Depends(require_permission("production.lot_manage"))])
def update_lot_api(lot_id: int, obj_in: LotUpdate, db: Session = Depends(get_db)):
    lot = get_lot(db, lot_id)
    return _to_out(db, update_lot(db, lot, obj_in))


@router.delete("/{lot_id}", dependencies=[Depends(require_permission("production.lot_manage"))])
def delete_lot_api(lot_id: int, db: Session = Depends(get_db)):
    lot = get_lot(db, lot_id)
    delete_lot(db, lot)
    return {"detail": "已删除"}


# ---- 流转日志 ----

@router.get("/{lot_id}/transactions", response_model=list[LotTransactionOut])
def list_transactions_api(lot_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return list_transactions(db, lot_id)


@router.post("/{lot_id}/transactions", response_model=LotTransactionOut, dependencies=[Depends(require_permission("production.lot_manage"))])
def add_transaction_api(
    lot_id: int,
    obj_in: LotTransactionCreate,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    # 强制 lot_id 一致
    obj_in.lot_id = lot_id
    return add_transaction(db, obj_in, cu.id, cu.username)


# ---- 谱系追溯 ----

@router.get("/{lot_id}/ancestors")
def get_ancestors_api(lot_id: int, depth: int = 10, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    """递归追溯所有上游 lot"""
    return get_ancestors(db, lot_id, depth)


@router.get("/{lot_id}/descendants")
def get_descendants_api(lot_id: int, depth: int = 10, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    """递归追溯所有下游 lot"""
    return get_descendants(db, lot_id, depth)


@router.post("/genealogy", dependencies=[Depends(require_permission("production.lot_manage"))])
def link_genealogy_api(obj_in: LotGenealogyCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    """绑定上游 lot -> 下游 lot 谱系"""
    g = link_genealogy(db, obj_in)
    return {"id": g.id, "parent_lot_id": g.parent_lot_id, "child_lot_id": g.child_lot_id}
