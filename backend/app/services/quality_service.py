from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    D8Report, D8Status, FMEA, FMEAItem, WorkOrder, WorkOrderType, WorkOrderStatus,
    Equipment, SparePartMovement,
)
from app.schemas import (
    D8ReportCreate, D8ReportUpdate, FMEACreate, FMEAUpdate,
)


# ============ 8D 报告 ============

def _gen_d8_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count_today = db.query(D8Report).filter(D8Report.report_no.like(f"8D{today}%")).count()
    return f"8D{today}{count_today + 1:03d}"


def list_d8_reports(
    db: Session, equipment_id: Optional[int] = None, status: Optional[D8Status] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(D8Report)
    if equipment_id:
        q = q.filter(D8Report.equipment_id == equipment_id)
    if status:
        q = q.filter(D8Report.status == status)
    return q.order_by(D8Report.id.desc()).offset(skip).limit(limit).all()


def get_d8_report(db: Session, d8_id: int) -> Optional[D8Report]:
    return db.query(D8Report).filter(D8Report.id == d8_id).first()


def create_d8_report(db: Session, obj_in: D8ReportCreate) -> D8Report:
    eq = db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    data = obj_in.model_dump()
    rpt = D8Report(report_no=_gen_d8_no(db), **data)
    db.add(rpt)
    db.commit()
    db.refresh(rpt)
    return rpt


def update_d8_report(db: Session, rpt: D8Report, obj_in: D8ReportUpdate) -> D8Report:
    data = obj_in.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status == D8Status.CLOSED and rpt.status != D8Status.CLOSED:
        data["closed_at"] = datetime.utcnow()
    elif new_status and new_status != D8Status.CLOSED:
        data["closed_at"] = None
    for k, v in data.items():
        setattr(rpt, k, v)
    rpt.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rpt)
    return rpt


def delete_d8_report(db: Session, d8_id: int):
    rpt = get_d8_report(db, d8_id)
    if not rpt:
        raise HTTPException(status_code=404, detail="8D 报告不存在")
    db.delete(rpt)
    db.commit()


# ============ FMEA ============

def list_fmeas(db: Session, equipment_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    q = db.query(FMEA)
    if equipment_id:
        q = q.filter(FMEA.equipment_id == equipment_id)
    return q.order_by(FMEA.id.desc()).offset(skip).limit(limit).all()


def get_fmea(db: Session, fmea_id: int) -> Optional[FMEA]:
    return db.query(FMEA).filter(FMEA.id == fmea_id).first()


def _compute_rpn(item: FMEAItem):
    item.rpn = (item.severity or 0) * (item.occurrence or 0) * (item.detection or 0)


def create_fmea(db: Session, obj_in: FMEACreate) -> FMEA:
    eq = db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    data = obj_in.model_dump()
    items_data = data.pop("items", [])
    fmea = FMEA(**data)
    db.add(fmea)
    db.flush()
    for it in items_data:
        item = FMEAItem(fmea_id=fmea.id, **it)
        _compute_rpn(item)
        db.add(item)
    db.commit()
    db.refresh(fmea)
    return fmea


def update_fmea(db: Session, fmea: FMEA, obj_in: FMEAUpdate) -> FMEA:
    data = obj_in.model_dump(exclude_unset=True)
    items_data = data.pop("items", None)
    for k, v in data.items():
        setattr(fmea, k, v)
    if items_data is not None:
        db.query(FMEAItem).filter(FMEAItem.fmea_id == fmea.id).delete()
        for it in items_data:
            item = FMEAItem(fmea_id=fmea.id, **it)
            _compute_rpn(item)
            db.add(item)
    fmea.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(fmea)
    return fmea


def delete_fmea(db: Session, fmea_id: int):
    fmea = get_fmea(db, fmea_id)
    if not fmea:
        raise HTTPException(status_code=404, detail="FMEA 不存在")
    db.delete(fmea)
    db.commit()


def add_fmea_item(db: Session, fmea: FMEA, item_data: dict) -> FMEAItem:
    item = FMEAItem(fmea_id=fmea.id, **item_data)
    _compute_rpn(item)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_fmea_item(db: Session, item: FMEAItem, item_data: dict) -> FMEAItem:
    for k, v in item_data.items():
        setattr(item, k, v)
    _compute_rpn(item)
    db.commit()
    db.refresh(item)
    return item


# ============ 可靠性指标: MTBF / MTTR / 成本 ============

def _hours(start: Optional[datetime], end: Optional[datetime]) -> float:
    if not start or not end:
        return 0.0
    if end <= start:
        return 0.0
    return (end - start).total_seconds() / 3600.0


def reliability_metrics(
    db: Session,
    equipment_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    """计算 MTBF / MTTR / 故障次数 / 停机时长 / 备件成本。

    MTTR = 完成维修工单(实际起止)的平均修复时长(小时)
    MTBF = (观测时长 - 总停机时长) / 故障次数；无故障时取观测时长
    """
    now = datetime.utcnow()
    period_start = start or (now - timedelta(days=30))
    period_end = end or now

    wq = db.query(WorkOrder).filter(
        WorkOrder.type == WorkOrderType.REPAIR,
        WorkOrder.status == WorkOrderStatus.COMPLETED,
    )
    if equipment_id:
        wq = wq.filter(WorkOrder.equipment_id == equipment_id)
    work_orders = wq.order_by(WorkOrder.actual_end.asc()).all()

    repair_hours_list = []
    failure_events = []
    for wo in work_orders:
        if wo.actual_start and wo.actual_end:
            h = _hours(wo.actual_start, wo.actual_end)
            repair_hours_list.append(h)
            failure_events.append((wo.actual_start, wo.actual_end, h))

    failure_count = len(failure_events)
    total_repair_hours = sum(repair_hours_list)
    mttr_hours = (total_repair_hours / failure_count) if failure_count else 0.0

    # 停机时长：用故障工单的实际起止之和（与 MTTR 同口径，便于本地轻量部署）
    total_downtime_hours = total_repair_hours
    observation_hours = (period_end - period_start).total_seconds() / 3600.0
    uptime_hours = max(0.0, observation_hours - total_downtime_hours)
    mtbf_hours = (uptime_hours / failure_count) if failure_count else observation_hours

    # 备件消耗成本：OUT 出库 * 单价
    mq = db.query(SparePartMovement).filter(SparePartMovement.movement_type == "OUT")
    if equipment_id:
        # 通过 work_order -> spare_part_usage -> movement 关联较复杂，这里近似按时间窗口汇总
        mq = mq.filter(SparePartMovement.created_at >= period_start, SparePartMovement.created_at <= period_end)
    else:
        mq = mq.filter(SparePartMovement.created_at >= period_start, SparePartMovement.created_at <= period_end)
    movements = mq.all()
    spare_cost = 0.0
    for mv in movements:
        sp = mv.spare_part
        price = (sp.unit_price or 0) if sp else 0
        spare_cost += (mv.qty or 0) * price

    return {
        "period_start": period_start,
        "period_end": period_end,
        "equipment_id": equipment_id,
        "failure_count": failure_count,
        "total_repair_hours": round(total_repair_hours, 2),
        "total_downtime_hours": round(total_downtime_hours, 2),
        "mttr_hours": round(mttr_hours, 2),
        "mtbf_hours": round(mtbf_hours, 2),
        "spare_cost": round(spare_cost, 2),
    }
