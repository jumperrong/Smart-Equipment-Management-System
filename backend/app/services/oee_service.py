"""OEE / WIP 实时看板服务。

设备 OEE = 可用率(Availability) × 性能率(Performance) × 质量率(Quality)：
  - Availability = run_minutes / planned_minutes（理想耗时）
  - Performance  = 理论产出耗时 / run_minutes
  - Quality      = good_qty / total_qty
WIP：聚合未完工派工（ASSIGNED/RUNNING/QUEUED/HELD），按工序与产品分组。
"""
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ProductionRecord, Dispatch, DispatchStatus, Equipment,
    ProductionOrder, Product,
)
from app.schemas import OEEWIPDashboardOut, EquipmentOEEOut, WIPByStepOut


def _round4(v) -> float:
    return round(float(v or 0), 4)


def get_oee_wip_dashboard(
    db: Session,
    days: int = 7,
    equipment_id: int | None = None,
) -> OEEWIPDashboardOut:
    """OEE / WIP 看板：按设备聚合 OEE，按工序聚合在制 WIP。"""
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    # ============ 设备 OEE 聚合 ============
    q = db.query(ProductionRecord).filter(ProductionRecord.start_time >= period_start)
    if equipment_id:
        q = q.filter(ProductionRecord.equipment_id == equipment_id)
    records = q.all()

    # 按设备分组
    eq_groups: dict[int, list[ProductionRecord]] = {}
    for r in records:
        eq_groups.setdefault(r.equipment_id, []).append(r)

    eq_ids = list(eq_groups.keys())
    eq_map: dict[int, Equipment] = {}
    if eq_ids:
        eq_map = {e.id: e for e in db.query(Equipment).filter(Equipment.id.in_(eq_ids)).all()}

    equipment_oee: list[EquipmentOEEOut] = []
    # 总体加权累加器
    sum_run = 0.0
    sum_planned = 0.0
    sum_good = 0
    sum_total = 0
    sum_theory_output = 0.0

    for eq_id, recs in eq_groups.items():
        eq = eq_map.get(eq_id)
        run_minutes = float(sum((r.duration_minutes or 0) for r in recs))
        good_qty = int(sum((r.good_qty or 0) for r in recs))
        total_qty = int(sum(((r.good_qty or 0) + (r.defect_qty or 0)) for r in recs))

        # 解析理想节拍：优先取生产记录快照，兜底设备 theoretical_cycle
        ideal_cycle_sec: float | None = None
        for r in recs:
            if r.ideal_cycle:
                ideal_cycle_sec = float(r.ideal_cycle)
                break
        if ideal_cycle_sec is None and eq is not None and eq.theoretical_cycle:
            ideal_cycle_sec = float(eq.theoretical_cycle)

        if ideal_cycle_sec is None:
            # 兜底：无节拍信息，planned=run（可用率=1.0），性能率=1.0
            planned_minutes = run_minutes
            theory_output_minutes = run_minutes
            performance = 1.0
        else:
            planned_minutes = 0.0
            for r in recs:
                base_qty = (r.input_qty if r.input_qty else r.plan_qty) or 0
                planned_minutes += base_qty * ideal_cycle_sec / 60.0
            theory_output_minutes = total_qty * ideal_cycle_sec / 60.0
            performance = (theory_output_minutes / run_minutes) if run_minutes > 0 else 0.0

        # 可用率：>1 截 1.0，分母为 0 时取 0
        if planned_minutes > 0:
            availability = min(run_minutes / planned_minutes, 1.0)
        else:
            availability = 0.0
        # 质量率
        quality = (good_qty / total_qty) if total_qty > 0 else 0.0
        oee = availability * performance * quality

        equipment_oee.append(EquipmentOEEOut(
            equipment_id=eq_id,
            equipment_name=eq.name if eq else None,
            run_minutes=_round4(run_minutes),
            planned_minutes=_round4(planned_minutes),
            good_qty=good_qty,
            total_qty=total_qty,
            availability=_round4(availability),
            performance=_round4(performance),
            quality=_round4(quality),
            oee=_round4(oee),
            ideal_cycle_sec=ideal_cycle_sec,
        ))

        sum_run += run_minutes
        sum_planned += planned_minutes
        sum_good += good_qty
        sum_total += total_qty
        sum_theory_output += theory_output_minutes

    # ============ 总体 OEE（加权平均）============
    overall_availability = (sum_run / sum_planned) if sum_planned > 0 else 0.0
    overall_performance = (sum_theory_output / sum_run) if sum_run > 0 else 0.0
    overall_quality = (sum_good / sum_total) if sum_total > 0 else 0.0
    overall_oee = overall_availability * overall_performance * overall_quality

    # ============ WIP 按工序聚合 ============
    # 未完工派工：ASSIGNED/RUNNING/QUEUED/HELD
    # dispatch 可能无 production_order 关系，用 outerjoin 兜底取 product.code
    wip_rows = (
        db.query(
            Dispatch.step_seq,
            Dispatch.step_name,
            Product.code,
            func.sum(Dispatch.wip_qty).label("wip_qty"),
            func.count(Dispatch.id).label("dispatch_count"),
        )
        .select_from(Dispatch)
        .outerjoin(ProductionOrder, ProductionOrder.id == Dispatch.mo_id)
        .outerjoin(Product, Product.id == ProductionOrder.product_id)
        .filter(Dispatch.status.in_([
            DispatchStatus.ASSIGNED.value,
            DispatchStatus.RUNNING.value,
            DispatchStatus.QUEUED.value,
            DispatchStatus.HELD.value,
        ]))
        .group_by(Dispatch.step_seq, Dispatch.step_name, Product.code)
        .all()
    )

    wip_by_step: list[WIPByStepOut] = []
    total_wip_qty = 0
    for row in wip_rows:
        wip_qty = int(row.wip_qty or 0)
        total_wip_qty += wip_qty
        wip_by_step.append(WIPByStepOut(
            step_seq=row.step_seq,
            step_name=row.step_name,
            product_code=row.code,
            wip_qty=wip_qty,
            dispatch_count=int(row.dispatch_count or 0),
        ))

    return OEEWIPDashboardOut(
        period_start=period_start,
        period_end=period_end,
        equipment_oee=equipment_oee,
        wip_by_step=wip_by_step,
        total_wip_qty=total_wip_qty,
        overall_oee=_round4(overall_oee),
    )
