from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import WorkOrderType, WorkOrderStatus, UserRole
from app.schemas import (
    WorkOrderCreate, WorkOrderOut, WorkOrderUpdate, FaultAnalysisIn,
    SparePartUsageIn, RepairReportCreate, RepairReportOut,
    PMPlanCreate, PMPlanUpdate, PMPlanOut,
)
from app.services import work_order_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/work-orders", tags=["工单管理"])


@router.get("", response_model=list[WorkOrderOut])
def list_work_orders(
    equipment_id: Optional[int] = None,
    type: Optional[WorkOrderType] = None,
    status: Optional[WorkOrderStatus] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return work_order_service.list_work_orders(db, equipment_id=equipment_id, type=type, status=status, skip=skip, limit=limit)


@router.post("", response_model=WorkOrderOut, dependencies=[Depends(require_permission("work_order.write"))])
def create_work_order(obj_in: WorkOrderCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return work_order_service.create_work_order(db, obj_in, current_user)


# PM 计划（必须在 /{wo_id} 之前 include，避免 "pm-plans" 被路径参数捕获）
pm_router = APIRouter(prefix="/pm-plans", tags=["PM维护计划"])


@pm_router.get("", response_model=list[PMPlanOut])
def list_pm_plans(
    equipment_id: Optional[int] = None, skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return work_order_service.list_pm_plans(db, equipment_id=equipment_id, skip=skip, limit=limit)


@pm_router.post("", response_model=PMPlanOut, dependencies=[Depends(require_permission("pm_plan.write"))])
def create_pm_plan(obj_in: PMPlanCreate, db: Session = Depends(get_db)):
    return work_order_service.create_pm_plan(db, obj_in)


@pm_router.put("/{plan_id}", response_model=PMPlanOut, dependencies=[Depends(require_permission("pm_plan.write"))])
def update_pm_plan(plan_id: int, obj_in: PMPlanUpdate, db: Session = Depends(get_db)):
    return work_order_service.update_pm_plan(db, plan_id, obj_in)


@pm_router.get("/calendar", dependencies=[Depends(get_current_user)])
def get_pm_calendar(
    start: datetime = Query(..., description="ISO 时间范围起点(包含)"),
    end: datetime = Query(..., description="ISO 时间范围终点(包含)"),
    equipment_id: Optional[int] = Query(None, description="按设备过滤"),
    db: Session = Depends(get_db),
):
    return work_order_service.get_pm_calendar(db, start, end, equipment_id=equipment_id)


@pm_router.delete("/{plan_id}", dependencies=[Depends(require_permission("pm_plan.delete"))])
def delete_pm_plan(plan_id: int, db: Session = Depends(get_db)):
    work_order_service.delete_pm_plan(db, plan_id)
    return {"ok": True}


@pm_router.post("/generate-due", dependencies=[Depends(require_permission("pm_plan.generate_due"))])
def generate_due_plans(db: Session = Depends(get_db)):
    """手动触发：生成所有到期的 PM 工单"""
    count = work_order_service.generate_pm_work_orders(db)
    return {"generated": count}


router.include_router(pm_router)


# 报修单（同样需在 /{wo_id} 之前 include）
reports_router = APIRouter(prefix="/reports", tags=["报修单"])


@reports_router.get("", response_model=list[RepairReportOut])
def list_reports(
    equipment_id: Optional[int] = None, status: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    return work_order_service.list_reports(db, equipment_id=equipment_id, status=status, skip=skip, limit=limit)


@reports_router.post("", response_model=RepairReportOut, dependencies=[Depends(require_permission("repair_report.create"))])
def create_report(obj_in: RepairReportCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return work_order_service.create_report(db, obj_in, current_user)


@reports_router.post("/{report_id}/convert", response_model=WorkOrderOut, dependencies=[Depends(require_permission("repair_report.convert"))])
def convert_report(report_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return work_order_service.convert_report_to_work_order(db, report_id, current_user)


router.include_router(reports_router)


@router.get("/{wo_id}", response_model=WorkOrderOut)
def get_work_order(wo_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    wo = work_order_service.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    return wo


@router.put("/{wo_id}", response_model=WorkOrderOut, dependencies=[Depends(require_permission("work_order.write"))])
def update_work_order(wo_id: int, obj_in: WorkOrderUpdate, db: Session = Depends(get_db)):
    wo = work_order_service.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    return work_order_service.update_work_order(db, wo, obj_in)


@router.put("/{wo_id}/fault-analysis", response_model=WorkOrderOut, dependencies=[Depends(require_permission("work_order.fault_analysis"))])
def save_fault_analysis(wo_id: int, obj_in: FaultAnalysisIn, db: Session = Depends(get_db)):
    wo = work_order_service.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    return work_order_service.save_fault_analysis(db, wo, obj_in)


@router.get("/{wo_id}/five-whys", dependencies=[Depends(get_current_user)])
def list_five_whys(wo_id: int, db: Session = Depends(get_db)):
    rows = work_order_service.list_five_whys(db, wo_id)
    return [{"id": r.id, "seq": r.seq, "question": r.question, "answer": r.answer} for r in rows]


@router.post("/{wo_id}/spare-usages", dependencies=[Depends(require_permission("work_order.spare_usage"))])
def add_spare_usage(
    wo_id: int, obj_in: SparePartUsageIn,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    wo = work_order_service.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    return work_order_service.add_spare_usage(db, wo, obj_in, current_user)


@router.get("/{wo_id}/spare-usages", dependencies=[Depends(get_current_user)])
def list_spare_usages(wo_id: int, db: Session = Depends(get_db)):
    rows = work_order_service.list_spare_usages(db, wo_id)
    return [
        {
            "id": r.id, "work_order_id": r.work_order_id,
            "spare_part_id": r.spare_part_id, "qty": r.qty, "remark": r.remark,
        }
        for r in rows
    ]
