from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import LaborReportCreate, LaborReportUpdate, LaborReportOut
from app.services.labor_report_service import (
    list_labor_reports, get_labor_report, create_labor_report, update_labor_report, delete_labor_report
)

router = APIRouter(prefix="/labor-reports", tags=["报工"])


@router.get("", response_model=list[LaborReportOut])
def list_labor_reports_api(
    dispatch_id: int | None = Query(None),
    reporter_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return list_labor_reports(db, dispatch_id=dispatch_id, reporter_id=reporter_id, skip=skip, limit=limit)


@router.get("/{report_id}", response_model=LaborReportOut)
def get_labor_report_api(report_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return get_labor_report(db, report_id)


@router.post("", response_model=LaborReportOut, dependencies=[Depends(require_permission("production.labor_report"))])
def create_labor_report_api(obj_in: LaborReportCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return create_labor_report(db, obj_in, cu.id, cu.username)


@router.put("/{report_id}", response_model=LaborReportOut, dependencies=[Depends(require_permission("production.labor_correct"))])
def update_labor_report_api(report_id: int, obj_in: LaborReportUpdate, db: Session = Depends(get_db)):
    r = get_labor_report(db, report_id)
    return update_labor_report(db, r, obj_in)


@router.delete("/{report_id}", dependencies=[Depends(require_permission("production.labor_correct"))])
def delete_labor_report_api(report_id: int, db: Session = Depends(get_db)):
    r = get_labor_report(db, report_id)
    delete_labor_report(db, r)
    return {"detail": "已删除"}
