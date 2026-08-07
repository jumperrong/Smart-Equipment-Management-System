from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    AssetInventory, AssetInventoryLine, InventoryStatus,
    AssetApplication, ApplicationType, ApplicationStatus, Equipment,
)
from app.schemas import (
    AssetInventoryCreate, AssetInventoryLineUpdate,
    AssetApplicationCreate, AssetApplicationApprove,
)


# ============ 资产盘点 ============

def _gen_inv_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count_today = db.query(AssetInventory).filter(AssetInventory.inventory_no.like(f"INV{today}%")).count()
    return f"INV{today}{count_today + 1:03d}"


def list_inventories(db: Session, status: Optional[InventoryStatus] = None, skip: int = 0, limit: int = 100):
    q = db.query(AssetInventory)
    if status:
        q = q.filter(AssetInventory.status == status)
    return q.order_by(AssetInventory.id.desc()).offset(skip).limit(limit).all()


def get_inventory(db: Session, inv_id: int) -> Optional[AssetInventory]:
    return db.query(AssetInventory).filter(AssetInventory.id == inv_id).first()


def create_inventory(db: Session, obj_in: AssetInventoryCreate, creator_id: int) -> AssetInventory:
    data = obj_in.model_dump()
    equipment_ids = data.pop("equipment_ids", [])
    inv = AssetInventory(inventory_no=_gen_inv_no(db), created_by=creator_id, **data)
    db.add(inv)
    db.flush()
    if not equipment_ids:
        equipment_ids = [e.id for e in db.query(Equipment).filter(Equipment.is_active.is_(True)).all()]
    for eq_id in equipment_ids:
        eq = db.query(Equipment).filter(Equipment.id == eq_id).first()
        db.add(AssetInventoryLine(
            inventory_id=inv.id, equipment_id=eq_id,
            system_status=eq.current_status.value if eq else None,
            result="PENDING",
        ))
    db.commit()
    db.refresh(inv)
    return inv


def update_inventory_line(db: Session, line: AssetInventoryLine, obj_in: AssetInventoryLineUpdate,
                          checker_id: int) -> AssetInventoryLine:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(line, k, v)
    if line.result == "PENDING" and "result" not in data:
        # 根据勾选自动判定结果
        if line.actual_found and line.location_match:
            line.result = "MATCH"
        elif line.actual_found is True and line.location_match is False:
            line.result = "MISMATCH"
        elif line.actual_found is False:
            line.result = "MISSING"
    if line.result != "PENDING" and not line.checked_at:
        line.checked_by = checker_id
        line.checked_at = datetime.utcnow()
    db.commit()
    db.refresh(line)
    return line


def complete_inventory(db: Session, inv: AssetInventory) -> AssetInventory:
    pending = db.query(AssetInventoryLine).filter(
        AssetInventoryLine.inventory_id == inv.id, AssetInventoryLine.result == "PENDING"
    ).count()
    inv.status = InventoryStatus.COMPLETED
    inv.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(inv)
    return inv


def delete_inventory(db: Session, inv_id: int):
    inv = get_inventory(db, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="盘点任务不存在")
    db.delete(inv)
    db.commit()


# ============ 调拨 / 报废申请 ============

def _gen_app_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count_today = db.query(AssetApplication).filter(AssetApplication.application_no.like(f"APP{today}%")).count()
    return f"APP{today}{count_today + 1:03d}"


def list_applications(
    db: Session, type: Optional[ApplicationType] = None, status: Optional[ApplicationStatus] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(AssetApplication)
    if type:
        q = q.filter(AssetApplication.type == type)
    if status:
        q = q.filter(AssetApplication.status == status)
    return q.order_by(AssetApplication.id.desc()).offset(skip).limit(limit).all()


def get_application(db: Session, app_id: int) -> Optional[AssetApplication]:
    return db.query(AssetApplication).filter(AssetApplication.id == app_id).first()


def create_application(db: Session, obj_in: AssetApplicationCreate, applicant_id: int) -> AssetApplication:
    eq = db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    data = obj_in.model_dump()
    if not data.get("from_location") and eq.factory:
        data["from_location"] = f"{eq.factory or ''}/{eq.area or ''}".strip("/")
    app = AssetApplication(application_no=_gen_app_no(db), applicant_id=applicant_id, **data)
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def approve_application(db: Session, app: AssetApplication, obj_in: AssetApplicationApprove, approver_id: int) -> AssetApplication:
    if app.status != ApplicationStatus.PENDING:
        raise HTTPException(status_code=400, detail="该申请已处理")
    if obj_in.decision == "APPROVED":
        app.status = ApplicationStatus.APPROVED
    elif obj_in.decision == "REJECTED":
        app.status = ApplicationStatus.REJECTED
    else:
        raise HTTPException(status_code=400, detail="非法决定")
    app.approver_id = approver_id
    app.approved_at = datetime.utcnow()
    if obj_in.remark:
        app.remark = obj_in.remark
    db.commit()
    db.refresh(app)
    return app


def complete_application(db: Session, app: AssetApplication) -> AssetApplication:
    if app.status != ApplicationStatus.APPROVED:
        raise HTTPException(status_code=400, detail="仅已批准申请可执行完成")
    app.status = ApplicationStatus.COMPLETED
    app.completed_at = datetime.utcnow()
    eq = db.query(Equipment).filter(Equipment.id == app.equipment_id).first()
    if eq:
        if app.type == ApplicationType.SCRAP:
            eq.is_active = False
        elif app.type == ApplicationType.TRANSFER and app.to_location:
            parts = app.to_location.split("/", 1)
            eq.factory = parts[0] if parts[0] else eq.factory
            if len(parts) > 1 and parts[1]:
                eq.area = parts[1]
    db.commit()
    db.refresh(app)
    return app
