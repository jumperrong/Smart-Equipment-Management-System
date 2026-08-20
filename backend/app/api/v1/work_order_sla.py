from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import WorkOrder, WorkOrderStatus as WOS, User
from app.schemas import WorkOrderOut, SLASetRequest, SLAEscalateRequest
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/work-order-sla", tags=["工单SLA"])


def _recalc_sla(wo: WorkOrder) -> None:
    """根据工单当前状态计算实际响应/解决时长，并刷新 sla_breach 标志。

    - 实际响应时长：created_at → actual_start（首次受理），仅当已派工及之后状态
    - 实际解决时长：created_at → completed_at/actual_end（关闭）
    - 幂等：每次按当前时间字段重算，无副作用
    """
    now = datetime.utcnow()
    created = wo.created_at or now

    # 实际响应时长（创建 → 首次受理）
    if wo.actual_start and wo.status not in (WOS.CREATED,):
        if wo.actual_start >= created:
            wo.actual_response_minutes = int(
                (wo.actual_start - created).total_seconds() // 60
            )

    # 实际解决时长（创建 → 关闭）
    if wo.status in (WOS.COMPLETED, WOS.CANCELLED):
        closed_at = wo.completed_at or wo.actual_end or now
        if closed_at >= created:
            wo.actual_resolution_minutes = int(
                (closed_at - created).total_seconds() // 60
            )

    # 超期判定
    breach = False
    if (
        wo.sla_response_minutes is not None
        and wo.actual_response_minutes is not None
        and wo.actual_response_minutes > wo.sla_response_minutes
    ):
        breach = True
    if (
        wo.sla_resolution_minutes is not None
        and wo.actual_resolution_minutes is not None
        and wo.actual_resolution_minutes > wo.sla_resolution_minutes
    ):
        breach = True
    wo.sla_breach = breach


@router.get("/stats", dependencies=[Depends(require_permission("work_order.sla_manage"))])
def sla_stats(
    db: Session = Depends(get_db),
):
    """SLA 达成率统计：总数/超期数/达成数/达成率/平均响应/平均解决。

    统计范围：已设置 SLA 目标（sla_response_minutes 非空）的工单。
    统计前在内存中重算各工单 SLA（不落库），保证数据新鲜。
    """
    rows = (
        db.query(WorkOrder)
        .filter(WorkOrder.sla_response_minutes != None)  # noqa: E712
        .all()
    )
    # 内存重算，不 commit（保持 GET 无副作用）
    for wo in rows:
        _recalc_sla(wo)

    total = len(rows)
    breached = sum(1 for r in rows if r.sla_breach)
    achieved = total - breached if total else 0
    achieve_rate = round(achieved / total, 4) if total else 0.0
    resp_vals = [
        r.actual_response_minutes
        for r in rows
        if r.actual_response_minutes is not None
    ]
    res_vals = [
        r.actual_resolution_minutes
        for r in rows
        if r.actual_resolution_minutes is not None
    ]
    avg_resp = round(sum(resp_vals) / len(resp_vals), 2) if resp_vals else 0.0
    avg_res = round(sum(res_vals) / len(res_vals), 2) if res_vals else 0.0
    return {
        "total": total,
        "breached": breached,
        "achieved": achieved,
        "achieve_rate": achieve_rate,
        "avg_response_minutes": avg_resp,
        "avg_resolution_minutes": avg_res,
    }


@router.get("/breaches", response_model=List[WorkOrderOut], dependencies=[Depends(require_permission("work_order.sla_manage"))])
def list_breaches(
    db: Session = Depends(get_db),
):
    """查询所有 SLA 超期工单。"""
    rows = (
        db.query(WorkOrder)
        .filter(WorkOrder.sla_breach == True)  # noqa: E712
        .order_by(WorkOrder.created_at.desc())
        .all()
    )
    return rows


@router.put("/{order_id}/sla", response_model=WorkOrderOut, dependencies=[Depends(require_permission("work_order.assign"))])
def set_sla(
    order_id: int,
    obj_in: SLASetRequest,
    db: Session = Depends(get_db),
):
    """设置 SLA 目标（响应/解决时长，分钟）。"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if obj_in.sla_response_minutes is not None:
        wo.sla_response_minutes = obj_in.sla_response_minutes
    if obj_in.sla_resolution_minutes is not None:
        wo.sla_resolution_minutes = obj_in.sla_resolution_minutes
    _recalc_sla(wo)
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{order_id}/escalate", response_model=WorkOrderOut, dependencies=[Depends(require_permission("work_order.sla_manage"))])
def escalate(
    order_id: int,
    obj_in: SLAEscalateRequest,
    db: Session = Depends(get_db),
):
    """升级工单：标记已升级 + 指派给上级（可选同时改派负责人）。"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    target = db.query(User).filter(User.id == obj_in.escalate_to_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="升级目标用户不存在")
    wo.escalated = True
    wo.escalated_to_id = obj_in.escalate_to_user_id
    wo.escalated_at = datetime.utcnow()
    if obj_in.reassign:
        wo.assignee_id = obj_in.escalate_to_user_id
    _recalc_sla(wo)
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{order_id}/recalculate", response_model=WorkOrderOut, dependencies=[Depends(require_permission("work_order.sla_manage"))])
def recalculate(
    order_id: int,
    db: Session = Depends(get_db),
):
    """单独重算某工单的 actual_response/resolution_minutes 与 sla_breach。

    用于工单受理/关闭时未自动计算的场景，由具备 SLA 管理权限的角色手动触发。
    """
    wo = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    _recalc_sla(wo)
    db.commit()
    db.refresh(wo)
    return wo
