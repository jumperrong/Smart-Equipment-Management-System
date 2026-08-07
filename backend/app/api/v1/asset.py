from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import InventoryStatus, ApplicationType, ApplicationStatus, UserRole
from app.schemas import (
    AssetInventoryCreate, AssetInventoryOut, AssetInventoryLineUpdate, AssetInventoryLineOut,
    AssetApplicationCreate, AssetApplicationOut, AssetApplicationApprove,
)
from app.services import asset_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/assets", tags=["资产盘点/调拨报废"])


# ============ 资产盘点 ============

@router.get("/inventories", response_model=list[AssetInventoryOut])
def list_inventories(
    status: Optional[InventoryStatus] = None, skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return asset_service.list_inventories(db, status=status, skip=skip, limit=limit)


@router.post("/inventories", response_model=AssetInventoryOut, dependencies=[Depends(require_permission("asset.inventory_write"))])
def create_inventory(obj_in: AssetInventoryCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return asset_service.create_inventory(db, obj_in, current_user.id)


@router.get("/inventories/{inv_id}", response_model=AssetInventoryOut)
def get_inventory(inv_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    inv = asset_service.get_inventory(db, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="盘点任务不存在")
    return inv


@router.put("/inventories/{inv_id}/lines/{line_id}", response_model=AssetInventoryLineOut, dependencies=[Depends(require_permission("asset.inventory_line_update"))])
def update_inventory_line(inv_id: int, line_id: int, obj_in: AssetInventoryLineUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from app.models import AssetInventoryLine
    line = db.query(AssetInventoryLine).filter(
        AssetInventoryLine.id == line_id, AssetInventoryLine.inventory_id == inv_id
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="盘点明细不存在")
    return asset_service.update_inventory_line(db, line, obj_in, current_user.id)


@router.post("/inventories/{inv_id}/complete", response_model=AssetInventoryOut, dependencies=[Depends(require_permission("asset.inventory_write"))])
def complete_inventory(inv_id: int, db: Session = Depends(get_db)):
    inv = asset_service.get_inventory(db, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="盘点任务不存在")
    return asset_service.complete_inventory(db, inv)


@router.delete("/inventories/{inv_id}", dependencies=[Depends(require_permission("asset.inventory_delete"))])
def delete_inventory(inv_id: int, db: Session = Depends(get_db)):
    asset_service.delete_inventory(db, inv_id)
    return {"ok": True}


# ============ 调拨 / 报废申请 ============

@router.get("/applications", response_model=list[AssetApplicationOut])
def list_applications(
    type: Optional[ApplicationType] = None, status: Optional[ApplicationStatus] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return asset_service.list_applications(db, type=type, status=status, skip=skip, limit=limit)


@router.post("/applications", response_model=AssetApplicationOut, dependencies=[Depends(require_permission("asset.application_create"))])
def create_application(obj_in: AssetApplicationCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return asset_service.create_application(db, obj_in, current_user.id)


@router.get("/applications/{app_id}", response_model=AssetApplicationOut)
def get_application(app_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    app = asset_service.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请不存在")
    return app


@router.post("/applications/{app_id}/approve", response_model=AssetApplicationOut, dependencies=[Depends(require_permission("asset.application_approve"))])
def approve_application(app_id: int, obj_in: AssetApplicationApprove, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    app = asset_service.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请不存在")
    return asset_service.approve_application(db, app, obj_in, current_user.id)


@router.post("/applications/{app_id}/complete", response_model=AssetApplicationOut, dependencies=[Depends(require_permission("asset.application_complete"))])
def complete_application(app_id: int, db: Session = Depends(get_db)):
    app = asset_service.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请不存在")
    return asset_service.complete_application(db, app)
