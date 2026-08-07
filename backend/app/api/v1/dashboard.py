from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import UserRole
from app.schemas import (
    DashboardOut,
    ProductCreate, ProductUpdate, ProductOut,
    ProductionRecordCreate, ProductionRecordUpdate, ProductionRecordOut,
)
from app.services import production_service, dashboard_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(tags=["看板/产品/生产"])


# ---------- Dashboard ----------

@router.get("/dashboard", response_model=DashboardOut)
def dashboard(log_limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return dashboard_service.get_dashboard(db, log_limit=log_limit)


# ---------- Products ----------

prod_router = APIRouter(prefix="/products", tags=["产品"])


@prod_router.get("", response_model=list[ProductOut])
def list_products(active_only: bool = False, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return production_service.list_products(db, active_only=active_only)


@prod_router.post("", response_model=ProductOut, dependencies=[Depends(require_permission("production.product_write"))])
def create_product(obj_in: ProductCreate, db: Session = Depends(get_db)):
    return production_service.create_product(db, obj_in)


@prod_router.put("/{pid}", response_model=ProductOut, dependencies=[Depends(require_permission("production.product_write"))])
def update_product(pid: int, obj_in: ProductUpdate, db: Session = Depends(get_db)):
    obj = production_service.get_product(db, pid)
    if not obj:
        raise HTTPException(status_code=404, detail="产品不存在")
    return production_service.update_product(db, obj, obj_in)


@prod_router.delete("/{pid}", dependencies=[Depends(require_permission("production.product_delete"))])
def delete_product(pid: int, db: Session = Depends(get_db)):
    production_service.delete_product(db, pid)
    return {"ok": True}


# ---------- Production Records ----------

pr_router = APIRouter(prefix="/production-records", tags=["生产记录"])


@pr_router.get("", response_model=list[ProductionRecordOut])
def list_records(
    equipment_id: Optional[int] = None,
    product_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return production_service.list_production_records(
        db, equipment_id=equipment_id, product_id=product_id,
        start=start, end=end, skip=skip, limit=limit,
    )


@pr_router.post("", response_model=ProductionRecordOut, dependencies=[Depends(require_permission("production.record_create"))])
def create_record(obj_in: ProductionRecordCreate, db: Session = Depends(get_db)):
    return production_service.create_production_record(db, obj_in)


@pr_router.put("/{rid}", response_model=ProductionRecordOut, dependencies=[Depends(require_permission("production.record_update"))])
def update_record(rid: int, obj_in: ProductionRecordUpdate, db: Session = Depends(get_db)):
    obj = production_service.get_production_record(db, rid)
    if not obj:
        raise HTTPException(status_code=404, detail="生产记录不存在")
    return production_service.update_production_record(db, obj, obj_in)


@pr_router.delete("/{rid}", dependencies=[Depends(require_permission("production.record_delete"))])
def delete_record(rid: int, db: Session = Depends(get_db)):
    production_service.delete_production_record(db, rid)
    return {"ok": True}


router.include_router(prod_router)
router.include_router(pr_router)
