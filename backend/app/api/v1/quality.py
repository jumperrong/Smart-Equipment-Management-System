from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import D8Status, UserRole
from app.schemas import (
    D8ReportCreate, D8ReportOut, D8ReportUpdate,
    FMEACreate, FMEAOut, FMEAUpdate, FMEAItemCreate, FMEAItemOut,
)
from app.services import quality_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/quality", tags=["品管工具(8D/FMEA)"])


# ============ 8D 报告 ============

@router.get("/d8-reports", response_model=list[D8ReportOut])
def list_d8(
    equipment_id: Optional[int] = None, status: Optional[D8Status] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return quality_service.list_d8_reports(db, equipment_id=equipment_id, status=status, skip=skip, limit=limit)


@router.post("/d8-reports", response_model=D8ReportOut, dependencies=[Depends(require_permission("quality.d8_write"))])
def create_d8(obj_in: D8ReportCreate, db: Session = Depends(get_db)):
    return quality_service.create_d8_report(db, obj_in)


@router.get("/d8-reports/{d8_id}", response_model=D8ReportOut)
def get_d8(d8_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rpt = quality_service.get_d8_report(db, d8_id)
    if not rpt:
        raise HTTPException(status_code=404, detail="8D 报告不存在")
    return rpt


@router.put("/d8-reports/{d8_id}", response_model=D8ReportOut, dependencies=[Depends(require_permission("quality.d8_write"))])
def update_d8(d8_id: int, obj_in: D8ReportUpdate, db: Session = Depends(get_db)):
    rpt = quality_service.get_d8_report(db, d8_id)
    if not rpt:
        raise HTTPException(status_code=404, detail="8D 报告不存在")
    return quality_service.update_d8_report(db, rpt, obj_in)


@router.delete("/d8-reports/{d8_id}", dependencies=[Depends(require_permission("quality.d8_delete"))])
def delete_d8(d8_id: int, db: Session = Depends(get_db)):
    quality_service.delete_d8_report(db, d8_id)
    return {"ok": True}


# ============ FMEA ============

@router.get("/fmeas", response_model=list[FMEAOut])
def list_fmea(
    equipment_id: Optional[int] = None, skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return quality_service.list_fmeas(db, equipment_id=equipment_id, skip=skip, limit=limit)


@router.post("/fmeas", response_model=FMEAOut, dependencies=[Depends(require_permission("quality.fmea_write"))])
def create_fmea(obj_in: FMEACreate, db: Session = Depends(get_db)):
    return quality_service.create_fmea(db, obj_in)


@router.get("/fmeas/{fmea_id}", response_model=FMEAOut)
def get_fmea(fmea_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    fmea = quality_service.get_fmea(db, fmea_id)
    if not fmea:
        raise HTTPException(status_code=404, detail="FMEA 不存在")
    return fmea


@router.put("/fmeas/{fmea_id}", response_model=FMEAOut, dependencies=[Depends(require_permission("quality.fmea_write"))])
def update_fmea(fmea_id: int, obj_in: FMEAUpdate, db: Session = Depends(get_db)):
    fmea = quality_service.get_fmea(db, fmea_id)
    if not fmea:
        raise HTTPException(status_code=404, detail="FMEA 不存在")
    return quality_service.update_fmea(db, fmea, obj_in)


@router.delete("/fmeas/{fmea_id}", dependencies=[Depends(require_permission("quality.fmea_delete"))])
def delete_fmea(fmea_id: int, db: Session = Depends(get_db)):
    quality_service.delete_fmea(db, fmea_id)
    return {"ok": True}


@router.post("/fmeas/{fmea_id}/items", response_model=FMEAItemOut, dependencies=[Depends(require_permission("quality.fmea_write"))])
def add_fmea_item(fmea_id: int, obj_in: FMEAItemCreate, db: Session = Depends(get_db)):
    fmea = quality_service.get_fmea(db, fmea_id)
    if not fmea:
        raise HTTPException(status_code=404, detail="FMEA 不存在")
    return quality_service.add_fmea_item(db, fmea, obj_in.model_dump())


@router.put("/fmeas/{fmea_id}/items/{item_id}", response_model=FMEAItemOut, dependencies=[Depends(require_permission("quality.fmea_write"))])
def update_fmea_item(fmea_id: int, item_id: int, obj_in: FMEAItemCreate, db: Session = Depends(get_db)):
    from app.models import FMEAItem
    item = db.query(FMEAItem).filter(FMEAItem.id == item_id, FMEAItem.fmea_id == fmea_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="FMEA 条目不存在")
    return quality_service.update_fmea_item(db, item, obj_in.model_dump())


@router.delete("/fmeas/{fmea_id}/items/{item_id}", dependencies=[Depends(require_permission("quality.fmea_delete"))])
def delete_fmea_item(fmea_id: int, item_id: int, db: Session = Depends(get_db)):
    from app.models import FMEAItem
    item = db.query(FMEAItem).filter(FMEAItem.id == item_id, FMEAItem.fmea_id == fmea_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="FMEA 条目不存在")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ============ 可靠性指标 MTBF / MTTR ============

@router.get("/reliability")
def reliability(
    equipment_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return quality_service.reliability_metrics(db, equipment_id=equipment_id, start=start, end=end)
