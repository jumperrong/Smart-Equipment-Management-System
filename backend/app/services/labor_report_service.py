from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import (
    LaborReport, Dispatch, DispatchStatus, ProductionOrder, ProductionOrderStatus,
    ProductionRecord, DispatchStatus,
)
from app.schemas import LaborReportCreate, LaborReportUpdate


def list_labor_reports(db: Session, dispatch_id: int | None = None, reporter_id: int | None = None, skip: int = 0, limit: int = 50):
    q = db.query(LaborReport)
    if dispatch_id:
        q = q.filter(LaborReport.dispatch_id == dispatch_id)
    if reporter_id:
        q = q.filter(LaborReport.reporter_id == reporter_id)
    return q.order_by(LaborReport.id.desc()).offset(skip).limit(limit).all()


def get_labor_report(db: Session, report_id: int) -> LaborReport:
    r = db.query(LaborReport).filter(LaborReport.id == report_id).first()
    if not r:
        raise HTTPException(404, "报工记录不存在")
    return r


def create_labor_report(db: Session, obj_in: LaborReportCreate, user_id: int, user_name: str) -> LaborReport:
    dispatch = db.query(Dispatch).filter(Dispatch.id == obj_in.dispatch_id).first()
    if not dispatch:
        raise HTTPException(404, "派工单不存在")
    if dispatch.status not in (DispatchStatus.RUNNING.value, DispatchStatus.COMPLETED.value):
        raise HTTPException(400, f"派工单状态为 {dispatch.status}，不可报工")
    report = LaborReport(
        dispatch_id=obj_in.dispatch_id,
        reporter_id=user_id,
        reporter_name=user_name,
        session_start=obj_in.session_start,
        session_end=obj_in.session_end,
        input_qty=obj_in.input_qty,
        good_qty=obj_in.good_qty,
        defect_qty=obj_in.defect_qty,
        defect_detail=obj_in.defect_detail,
        operator_ids=obj_in.operator_ids,
        man_hours=obj_in.man_hours,
        form_record_id=obj_in.form_record_id,
        remark=obj_in.remark,
    )
    db.add(report)
    db.flush()
    
    # 联动：更新派工单完工数量
    dispatch.completed_qty = (dispatch.completed_qty or 0) + obj_in.good_qty
    dispatch.scrapped_qty = (dispatch.scrapped_qty or 0) + obj_in.defect_qty
    dispatch.wip_qty = max(0, (dispatch.dispatch_qty or 0) - dispatch.completed_qty - dispatch.scrapped_qty)
    
    # 联动：更新生产订单完工数量
    mo = dispatch.production_order
    if mo:
        mo.completed_qty = (mo.completed_qty or 0) + obj_in.good_qty
        mo.scrapped_qty = (mo.scrapped_qty or 0) + obj_in.defect_qty
        mo.input_qty = (mo.input_qty or 0) + obj_in.input_qty
        # 如果完工+报废 >= 计划，且该 MO 所有派工均已完工，自动完成 MO
        if mo.completed_qty + mo.scrapped_qty >= mo.plan_qty and mo.status == ProductionOrderStatus.IN_PROGRESS.value:
            sibling_dispatches = db.query(Dispatch).filter(Dispatch.mo_id == mo.id).all()
            all_done = all(
                d.status in (DispatchStatus.COMPLETED.value, DispatchStatus.SCRAPPED.value, DispatchStatus.CANCELLED.value)
                for d in sibling_dispatches
            )
            if all_done:
                mo.status = ProductionOrderStatus.COMPLETED.value
                mo.actual_end = datetime.utcnow()
    
    # 联动：写入生产记录(用于OEE计算)
    if dispatch.equipment_id and obj_in.good_qty > 0:
        pr = ProductionRecord(
            record_no=f"LR-{report.id:06d}",
            equipment_id=dispatch.equipment_id,
            product_id=mo.product_id if mo else None,
            batch_no=mo.batch_no if mo else None,
            plan_qty=obj_in.input_qty,
            input_qty=obj_in.input_qty,
            good_qty=obj_in.good_qty,
            defect_qty=obj_in.defect_qty,
            start_time=obj_in.session_start,
            end_time=obj_in.session_end or datetime.utcnow(),
            duration_minutes=obj_in.man_hours * 60 if obj_in.man_hours else None,
            operator_id=user_id,
        )
        db.add(pr)

    db.commit()
    db.refresh(report)

    # 联动：批次追溯 - 报工自动产出/流转 lot
    try:
        from app.services.lot_service import record_labor_report_lot
        record_labor_report_lot(db, report, user_id, user_name)
    except Exception as e:
        # lot 联动失败不影响报工本身，仅记录日志
        import traceback as _tb
        print(f"[lot_service] 报工 #{report.id} 批次联动失败: {e}")
        _tb.print_exc()

    return report


def update_labor_report(db: Session, report: LaborReport, obj_in: LaborReportUpdate) -> LaborReport:
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in data.items():
        setattr(report, k, v)
    db.commit()
    db.refresh(report)
    return report


def delete_labor_report(db: Session, report: LaborReport):
    """删除报工记录：必须反向回滚 Dispatch / MO 的累计数量，并清理对应 ProductionRecord。

    - 报工一旦删除，原累计到派工与 MO 的 good/defect/input 都需扣回
    - MO 若曾因此报工自动完工，回滚到 IN_PROGRESS 状态并清除 actual_end
    - 删除报工时联动写入的 ProductionRecord(record_no = LR-{report_id:06d})也一并清理
    """
    dispatch = report.dispatch
    if dispatch:
        dispatch.completed_qty = max(0, (dispatch.completed_qty or 0) - (report.good_qty or 0))
        dispatch.scrapped_qty = max(0, (dispatch.scrapped_qty or 0) - (report.defect_qty or 0))
        dispatch.wip_qty = max(0, (dispatch.dispatch_qty or 0) - dispatch.completed_qty - dispatch.scrapped_qty)

        mo = dispatch.production_order
        if mo:
            mo.completed_qty = max(0, (mo.completed_qty or 0) - (report.good_qty or 0))
            mo.scrapped_qty = max(0, (mo.scrapped_qty or 0) - (report.defect_qty or 0))
            mo.input_qty = max(0, (mo.input_qty or 0) - (report.input_qty or 0))
            # 若 MO 因该报工被自动完工，回滚到执行中
            if mo.status == ProductionOrderStatus.COMPLETED.value:
                mo.status = ProductionOrderStatus.IN_PROGRESS.value
                mo.actual_end = None

    # 清理联动写入的 ProductionRecord（按 LR-{report_id:06d} 命名规则）
    pr_no = f"LR-{report.id:06d}"
    db.query(ProductionRecord).filter(ProductionRecord.record_no == pr_no).delete(synchronize_session=False)

    db.delete(report)
    db.commit()
