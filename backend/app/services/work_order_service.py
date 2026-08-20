from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    WorkOrder, WorkOrderType, WorkOrderStatus, FiveWhy,
    PMPlan, Equipment, EquipmentStatus, User, SparePartUsage,
)
from app.schemas import (
    WorkOrderCreate, WorkOrderUpdate, FaultAnalysisIn, FiveWhyIn,
    PMPlanCreate, PMPlanUpdate, SparePartUsageIn,
)
from app.services import spare_part_service

# 工单状态合法流转表
VALID_WO_TRANSITIONS = {
    ("CREATED", "ASSIGNED"), ("CREATED", "CANCELLED"),
    ("ASSIGNED", "IN_PROGRESS"), ("ASSIGNED", "CANCELLED"),
    ("IN_PROGRESS", "PENDING_REVIEW"), ("IN_PROGRESS", "CANCELLED"),
    ("PENDING_REVIEW", "COMPLETED"), ("PENDING_REVIEW", "IN_PROGRESS"),
    ("COMPLETED", "PENDING_REVIEW"),  # 允许退回重审
}


def _gen_order_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count_today = (
        db.query(WorkOrder)
        .filter(WorkOrder.order_no.like(f"WO{today}%"))
        .count()
    )
    return f"WO{today}{count_today + 1:03d}"


def get_work_order(db: Session, wo_id: int) -> Optional[WorkOrder]:
    return db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()


def list_work_orders(
    db: Session,
    equipment_id: Optional[int] = None,
    type: Optional[WorkOrderType] = None,
    status: Optional[WorkOrderStatus] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(WorkOrder)
    if equipment_id:
        q = q.filter(WorkOrder.equipment_id == equipment_id)
    if type:
        q = q.filter(WorkOrder.type == type)
    if status:
        q = q.filter(WorkOrder.status == status)
    return q.order_by(WorkOrder.id.desc()).offset(skip).limit(limit).all()


def create_work_order(db: Session, obj_in: WorkOrderCreate, creator: User,
                      status_log_id: Optional[int] = None) -> WorkOrder:
    eq = db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")

    wo = WorkOrder(
        order_no=_gen_order_no(db),
        type=obj_in.type,
        status=WorkOrderStatus.CREATED,
        equipment_id=obj_in.equipment_id,
        title=obj_in.title,
        description=obj_in.description,
        assignee_id=obj_in.assignee_id,
        pm_plan_id=obj_in.pm_plan_id,
        status_log_id=status_log_id,
        urgency=(obj_in.urgency or "NORMAL").upper() if obj_in.urgency else "NORMAL",
        planned_start=obj_in.planned_start,
        planned_end=obj_in.planned_end,
        remark=obj_in.remark,
    )
    db.add(wo)
    db.flush()

    # 来源 PM 计划 → 更新上次执行/下次到期
    if obj_in.pm_plan_id:
        plan = db.query(PMPlan).filter(PMPlan.id == obj_in.pm_plan_id).first()
        if plan:
            plan.last_executed_at = datetime.utcnow()
            if plan.cycle_days:
                plan.next_due_date = datetime.utcnow() + timedelta(days=plan.cycle_days)

    db.commit()
    db.refresh(wo)
    return wo


def update_work_order(db: Session, wo: WorkOrder, obj_in: WorkOrderUpdate):
    data = obj_in.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status:
        if new_status == WorkOrderStatus.IN_PROGRESS and not wo.actual_start:
            data["actual_start"] = datetime.utcnow()
        elif new_status == WorkOrderStatus.COMPLETED:
            data["actual_end"] = datetime.utcnow()
            data["completed_at"] = datetime.utcnow()
    new_status = data.get("status")
    if new_status:
        old_status = wo.status.value if wo.status else None
        if old_status and old_status != new_status:
            if (old_status, new_status) not in VALID_WO_TRANSITIONS:
                from fastapi import HTTPException
                raise HTTPException(400, f"工单状态不允许从 {old_status} 跳转到 {new_status}")
    for k, v in data.items():
        setattr(wo, k, v)
    wo.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(wo)
    return wo


def save_fault_analysis(db: Session, wo: WorkOrder, obj_in: FaultAnalysisIn):
    data = obj_in.model_dump(exclude_unset=True)
    five_whys_data = data.pop("five_whys", None)
    for k, v in data.items():
        setattr(wo, k, v)
    if five_whys_data is not None:
        db.query(FiveWhy).filter(FiveWhy.work_order_id == wo.id).delete()
        for fw in five_whys_data:
            db.add(FiveWhy(work_order_id=wo.id, **fw))
    wo.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(wo)
    return wo


def list_five_whys(db: Session, wo_id: int) -> List[FiveWhy]:
    return (
        db.query(FiveWhy)
        .filter(FiveWhy.work_order_id == wo_id)
        .order_by(FiveWhy.seq.asc())
        .all()
    )


def add_spare_usage(
    db: Session, wo: WorkOrder, obj_in: SparePartUsageIn, operator: User
) -> dict:
    """工单领用备件 → 自动扣库存 + 记一笔 OUT 出库"""
    usage, movement = spare_part_service.consume_for_work_order(
        db,
        work_order_id=wo.id,
        spare_part_id=obj_in.spare_part_id,
        qty=obj_in.qty,
        operator_id=operator.id,
        remark=obj_in.remark,
    )
    db.commit()
    db.refresh(usage)
    return {
        "id": usage.id,
        "work_order_id": usage.work_order_id,
        "spare_part_id": usage.spare_part_id,
        "qty": usage.qty,
        "remark": usage.remark,
        "movement_id": usage.movement_id,
    }


def list_spare_usages(db: Session, wo_id: int):
    return (
        db.query(SparePartUsage)
        .filter(SparePartUsage.work_order_id == wo_id)
        .all()
    )


# ----- PM 计划 -----

def list_pm_plans(db: Session, equipment_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    q = db.query(PMPlan)
    if equipment_id:
        q = q.filter(PMPlan.equipment_id == equipment_id)
    return q.order_by(PMPlan.id.desc()).offset(skip).limit(limit).all()


def create_pm_plan(db: Session, obj_in: PMPlanCreate) -> PMPlan:
    eq = db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    plan = PMPlan(**obj_in.model_dump())
    if not plan.next_due_date and plan.cycle_days:
        plan.next_due_date = datetime.utcnow() + timedelta(days=plan.cycle_days)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def delete_pm_plan(db: Session, plan_id: int):
    plan = db.query(PMPlan).filter(PMPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="PM 计划不存在")
    db.delete(plan)
    db.commit()


def update_pm_plan(db: Session, plan_id: int, obj_in: PMPlanUpdate) -> PMPlan:
    plan = db.query(PMPlan).filter(PMPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="PM 计划不存在")
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan


def get_pm_calendar(db: Session, start_time: datetime, end_time: datetime,
                    equipment_id: Optional[int] = None):
    """返回 PM 日历视图：计划 PM 时间段 + 实际 PM 状态段

    planned_events: 按 PM 计划在 [start, end] 范围内展开（含历史周期）
    actual_events : 从 EquipmentStatusLog 里查 to_status = PM 的段
    """
    # 统一转成 naive UTC，与数据库存储一致
    if start_time.tzinfo is not None:
        start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
    if end_time.tzinfo is not None:
        end_time = end_time.astimezone(timezone.utc).replace(tzinfo=None)
    from app.models import EquipmentStatusLog, Equipment as _Eq

    # 1) 实际 PM 段：直接从状态日志拉 to_status=PM，与时间范围相交
    actual_q = (
        db.query(EquipmentStatusLog, _Eq.name.label("ename"), _Eq.asset_no.label("easset"))
        .join(_Eq, EquipmentStatusLog.equipment_id == _Eq.id)
        .filter(EquipmentStatusLog.to_status == EquipmentStatus.PM)
        .filter(EquipmentStatusLog.start_time <= end_time)
        .filter(
            (EquipmentStatusLog.end_time == None)
            | (EquipmentStatusLog.end_time >= start_time)
        )
    )
    if equipment_id:
        actual_q = actual_q.filter(EquipmentStatusLog.equipment_id == equipment_id)

    # 预查 PM Plan：建立 equipment_id -> planned_duration_minutes 映射（取该设备最新一条 active plan）
    plan_dur_map = {}
    plan_q0 = db.query(PMPlan.equipment_id, PMPlan.planned_duration_minutes).filter(PMPlan.is_active.is_(True))
    if equipment_id:
        plan_q0 = plan_q0.filter(PMPlan.equipment_id == equipment_id)
    for eq_id, dur in plan_q0.all():
        plan_dur_map[eq_id] = dur or 120

    actual_events = []
    import re as _re
    for lg, ename, easset in actual_q.order_by(EquipmentStatusLog.start_time.asc()).all():
        # 计算实际时长：进行中暂取到 now
        if lg.duration_minutes is not None:
            actual_dur = lg.duration_minutes
        elif lg.end_time is not None:
            actual_dur = round((lg.end_time - lg.start_time).total_seconds() / 60.0, 1)
        else:
            actual_dur = round((datetime.utcnow() - lg.start_time).total_seconds() / 60.0, 1)
        planned_dur = plan_dur_map.get(lg.equipment_id)
        # 超时判断：1) 已结束事件按实际时长对比；2) reason_detail 中含"超时 Xm"也视为超时（覆盖进行中事件）
        is_overtime = False
        overtime_extra = 0
        if lg.reason_detail:
            m = _re.search(r"超时\s*(\d+)\s*m", lg.reason_detail)
            if m:
                overtime_extra = int(m.group(1))
                is_overtime = True
        if (
            not is_overtime
            and planned_dur is not None
            and actual_dur is not None
            and actual_dur > planned_dur + 30
        ):
            is_overtime = True
            overtime_extra = max(0, round(actual_dur - planned_dur))
        # 进行中事件但 reason_detail 已声明超时：用 planned + overtime_extra 重算预估实际时长
        if is_overtime and planned_dur is not None and lg.end_time is None and lg.duration_minutes is None:
            actual_dur_for_show = planned_dur + overtime_extra
            # 进行中超时事件：实际结束预估 = 计划结束 + 超时分钟
            actual_end_for_show = lg.start_time + timedelta(minutes=planned_dur + overtime_extra)
        else:
            actual_dur_for_show = lg.duration_minutes or (
                None if not lg.end_time else round((lg.end_time - lg.start_time).total_seconds() / 60.0, 1)
            )
            actual_end_for_show = lg.end_time
        # 计划结束时间：实际开始 + 计划时长（前端用于拆分超时段）
        planned_end = (lg.start_time + timedelta(minutes=planned_dur)) if planned_dur is not None else None
        actual_events.append({
            "id": f"A{lg.id}",
            "type": "actual",
            "equipment_id": lg.equipment_id,
            "equipment_name": ename,
            "equipment_asset": easset,
            "start_time": lg.start_time,
            "end_time": actual_end_for_show,
            "duration_minutes": actual_dur_for_show,
            "planned_duration_minutes": planned_dur,
            "planned_end_time": planned_end,
            "is_overtime": is_overtime,
            "overtime_minutes": overtime_extra if is_overtime else 0,
            "reason_code": lg.reason_code,
            "reason_detail": lg.reason_detail,
        })

    # 2) 计划 PM 段：每个 PM Plan，按 cycle_days 周期扩展到 [start, end]
    plan_q = db.query(PMPlan, _Eq.name.label("ename"), _Eq.asset_no.label("easset")).join(
        _Eq, PMPlan.equipment_id == _Eq.id
    ).filter(PMPlan.is_active.is_(True))
    if equipment_id:
        plan_q = plan_q.filter(PMPlan.equipment_id == equipment_id)
    plan_rows = plan_q.all()

    planned_events = []
    gen_id = 0
    for plan, ename, easset in plan_rows:
        if not plan.next_due_date:
            continue
        start_hour = plan.planned_start_hour or 9
        duration = plan.planned_duration_minutes or 120
        # 以 next_due_date 为锚点，向前/向后按 cycle_days 展开
        anchor_due = plan.next_due_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # 向前查找最近 <= end_time 的起始周期锚点，同时保证 >= start_time
        # 计算需要向前退多少周期才能覆盖 start_time
        days_span = (end_time.date() - anchor_due.date()).days
        fwd_count = max(0, days_span // plan.cycle_days + 2)
        back_count = 0
        if (start_time.date() < anchor_due.date()):
            back_days = (anchor_due.date() - start_time.date()).days
            back_count = back_days // plan.cycle_days + 2

        seq = 0
        for i in range(-back_count, fwd_count + 1):
            seq += 1
            due_day = anchor_due + timedelta(days=i * plan.cycle_days)
            event_start = due_day + timedelta(hours=start_hour)
            event_end = event_start + timedelta(minutes=duration)
            if event_end < start_time or event_start > end_time:
                continue
            gen_id += 1
            planned_events.append({
                "id": f"P{plan.id}-{seq}",
                "type": "planned",
                "plan_id": plan.id,
                "plan_name": plan.name,
                "plan_items": plan.items or [],
                "equipment_id": plan.equipment_id,
                "equipment_name": ename,
                "equipment_asset": easset,
                "start_time": event_start,
                "end_time": event_end,
                "duration_minutes": duration,
            })
    planned_events.sort(key=lambda e: e["start_time"])
    return {"planned_events": planned_events, "actual_events": actual_events}


def generate_pm_work_orders(db: Session) -> int:
    """生成所有到期的 PM 工单（用于定时调用）。返回生成数量。"""
    now = datetime.utcnow()
    plans = (
        db.query(PMPlan)
        .filter(PMPlan.is_active.is_(True), PMPlan.next_due_date <= now)
        .all()
    )
    count = 0
    sys_user = db.query(User).filter(User.username == "admin").first()
    for plan in plans:
        create_work_order(
            db,
            WorkOrderCreate(
                type=WorkOrderType.PM,
                equipment_id=plan.equipment_id,
                title=f"PM: {plan.name}",
                description="; ".join(plan.items) if plan.items else "",
                pm_plan_id=plan.id,
            ),
            creator=sys_user or User(id=1, username="system", hashed_password="", role="admin"),
        )
        count += 1
    return count
