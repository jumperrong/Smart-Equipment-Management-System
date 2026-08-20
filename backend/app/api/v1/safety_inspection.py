from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import SafetyInspection, User
from app.schemas import (
    SafetyInspectionCreate,
    SafetyInspectionUpdate,
    SafetyInspectionOut,
    SafetyInspectionCheckIn,
)
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/safety-inspections", tags=["安全检查"])


# 频次 → 间隔天数
_FREQUENCY_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


def _compute_next_check_date(
    frequency: Optional[str], base: Optional[datetime] = None
) -> Optional[datetime]:
    if not frequency:
        return None
    days = _FREQUENCY_DAYS.get(frequency)
    if days is None:
        return None
    return (base or datetime.utcnow()) + timedelta(days=days)


@router.get("", response_model=List[SafetyInspectionOut], dependencies=[Depends(require_permission("safety.view"))])
def list_safety_inspections(
    equipment_id: Optional[int] = None,
    check_type: Optional[str] = None,
    result: Optional[str] = None,
    upcoming_days: Optional[int] = Query(
        None, description="过滤未来N天内到期的检查项"
    ),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(SafetyInspection)
    if equipment_id is not None:
        q = q.filter(SafetyInspection.equipment_id == equipment_id)
    if check_type:
        q = q.filter(SafetyInspection.check_type == check_type)
    if result:
        q = q.filter(SafetyInspection.result == result)
    if upcoming_days is not None:
        threshold = datetime.utcnow() + timedelta(days=upcoming_days)
        q = q.filter(
            SafetyInspection.next_check_date != None,  # noqa: E712
            SafetyInspection.next_check_date <= threshold,
        )
    rows = (
        q.order_by(SafetyInspection.next_check_date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows


@router.post("", response_model=SafetyInspectionOut, dependencies=[Depends(require_permission("safety.write"))])
def create_safety_inspection(
    obj_in: SafetyInspectionCreate,
    db: Session = Depends(get_db),
):
    data = obj_in.model_dump(exclude_unset=True)
    # 未显式提供 next_check_date 时按 frequency 自动计算
    if data.get("next_check_date") is None and data.get("frequency"):
        data["next_check_date"] = _compute_next_check_date(data["frequency"])
    obj = SafetyInspection(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/alerts", dependencies=[Depends(require_permission("safety.view"))])
def safety_alerts(
    db: Session = Depends(get_db),
):
    """告警：30天内到期 + 已过期（按 next_check_date 与 certificate_expiry 双维度）。"""
    now = datetime.utcnow()
    threshold = now + timedelta(days=30)
    rows = (
        db.query(SafetyInspection)
        .filter(
            (
                (SafetyInspection.next_check_date != None)  # noqa: E712
                & (SafetyInspection.next_check_date <= threshold)
            )
            | (
                (SafetyInspection.certificate_expiry != None)  # noqa: E712
                & (SafetyInspection.certificate_expiry <= threshold)
            )
        )
        .order_by(SafetyInspection.next_check_date.asc())
        .all()
    )

    expired = [
        r
        for r in rows
        if (r.next_check_date and r.next_check_date < now)
        or (r.certificate_expiry and r.certificate_expiry < now)
    ]
    expired_set = set(id(r) for r in expired)
    upcoming = [r for r in rows if id(r) not in expired_set]
    return {
        "total": len(rows),
        "expired_count": len(expired),
        "upcoming_count": len(upcoming),
        "expired": [SafetyInspectionOut.model_validate(r).model_dump() for r in expired],
        "upcoming": [SafetyInspectionOut.model_validate(r).model_dump() for r in upcoming],
    }


@router.put("/{inspection_id}", response_model=SafetyInspectionOut, dependencies=[Depends(require_permission("safety.write"))])
def update_safety_inspection(
    inspection_id: int,
    obj_in: SafetyInspectionUpdate,
    db: Session = Depends(get_db),
):
    obj = (
        db.query(SafetyInspection)
        .filter(SafetyInspection.id == inspection_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="安全检查记录不存在")
    data = obj_in.model_dump(exclude_unset=True)
    # 频次变更且未显式提供下次日期 → 重算
    if "frequency" in data and data.get("frequency") and data.get("next_check_date") is None:
        data["next_check_date"] = _compute_next_check_date(data["frequency"])
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{inspection_id}", dependencies=[Depends(require_permission("safety.write"))])
def delete_safety_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    obj = (
        db.query(SafetyInspection)
        .filter(SafetyInspection.id == inspection_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="安全检查记录不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/{inspection_id}/check", response_model=SafetyInspectionOut, dependencies=[Depends(require_permission("safety.write"))])
def perform_check(
    inspection_id: int,
    obj_in: SafetyInspectionCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行检查：记录结果 + 自动按频次计算下次检查日期。"""
    obj = (
        db.query(SafetyInspection)
        .filter(SafetyInspection.id == inspection_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="安全检查记录不存在")
    now = datetime.utcnow()
    obj.last_check_date = now
    obj.result = obj_in.result
    obj.findings = obj_in.findings
    obj.corrective_action = obj_in.corrective_action
    obj.checked_by_id = current_user.id
    obj.checked_by_name = current_user.full_name or current_user.username
    # 自动按频次计算下次检查日期
    obj.next_check_date = _compute_next_check_date(obj.frequency, now)
    db.commit()
    db.refresh(obj)
    return obj
