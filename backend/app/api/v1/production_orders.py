from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import ProductionOrderCreate, ProductionOrderUpdate, ProductionOrderOut
from app.services.production_order_service import (
    list_production_orders, get_production_order, create_production_order, update_production_order, delete_production_order
)

router = APIRouter(prefix="/production-orders", tags=["生产订单"])


@router.get("", response_model=list[ProductionOrderOut])
def list_production_orders_api(
    status: str | None = Query(None),
    product_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return list_production_orders(db, status=status, product_id=product_id, skip=skip, limit=limit)


@router.get("/{mo_id}", response_model=ProductionOrderOut)
def get_production_order_api(mo_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return get_production_order(db, mo_id)


@router.post("", response_model=ProductionOrderOut, dependencies=[Depends(require_permission("production.mo_manage"))])
def create_production_order_api(obj_in: ProductionOrderCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return create_production_order(db, obj_in, cu.id, cu.username)


@router.put("/{mo_id}", response_model=ProductionOrderOut, dependencies=[Depends(require_permission("production.mo_manage"))])
def update_production_order_api(mo_id: int, obj_in: ProductionOrderUpdate, db: Session = Depends(get_db)):
    mo = get_production_order(db, mo_id)
    return update_production_order(db, mo, obj_in)


@router.delete("/{mo_id}", dependencies=[Depends(require_permission("production.mo_manage"))])
def delete_production_order_api(mo_id: int, db: Session = Depends(get_db)):
    mo = get_production_order(db, mo_id)
    delete_production_order(db, mo)
    return {"detail": "已删除"}
