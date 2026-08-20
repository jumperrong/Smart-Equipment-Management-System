"""OEE / WIP 看板 API：实时设备 OEE 与按工序聚合的在制 WIP。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import OEEWIPDashboardOut
from app.services.oee_service import get_oee_wip_dashboard

router = APIRouter(prefix="/production-dashboard", tags=["OEE/WIP 看板"])


@router.get(
    "/oee-wip",
    response_model=OEEWIPDashboardOut,
    dependencies=[Depends(require_permission("production.oee_view"))],
)
def get_oee_wip_api(
    days: int = Query(7, ge=1, le=365),
    equipment_id: int | None = Query(None),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """获取 OEE/WIP 实时看板：设备 OEE + 按工序聚合的 WIP。"""
    return get_oee_wip_dashboard(db, days=days, equipment_id=equipment_id)
