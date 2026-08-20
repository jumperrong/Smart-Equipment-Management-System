"""设备保养 PM 到期提醒 API。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import PMReminderOut, PMReminderSummary
from app.services.pm_reminder_service import (
    list_pm_reminders,
    get_pm_reminder_summary,
)

router = APIRouter(prefix="/pm-reminders", tags=["PM 到期提醒"])


@router.get(
    "",
    response_model=list[PMReminderOut],
    dependencies=[Depends(require_permission("production.pm_reminder_view"))],
)
def list_pm_reminders_api(
    days_ahead: int = Query(7, ge=0),
    include_overdue: bool = Query(True),
    equipment_id: int | None = Query(None),
    only_active: bool = Query(True),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """列出 PM 到期/逾期提醒。"""
    return list_pm_reminders(
        db,
        days_ahead=days_ahead,
        include_overdue=include_overdue,
        equipment_id=equipment_id,
        only_active=only_active,
    )


@router.get(
    "/summary",
    response_model=PMReminderSummary,
    dependencies=[Depends(require_permission("production.pm_reminder_view"))],
)
def get_pm_reminder_summary_api(
    days_ahead: int = Query(7, ge=0),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """返回 PM 到期提醒汇总。"""
    return get_pm_reminder_summary(db, days_ahead=days_ahead)
