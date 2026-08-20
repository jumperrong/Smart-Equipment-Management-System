"""SPC 控制图 API：Xbar-R 控制图 + 数值字段清单。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import SPCChartOut
from app.services.spc_service import get_spc_chart, list_numeric_fields

router = APIRouter(prefix="/spc", tags=["SPC 控制图"])


@router.get("/chart", response_model=SPCChartOut, dependencies=[Depends(require_permission("production.spc_view"))])
def get_spc_chart_api(
    field_key: str = Query(..., description="模板字段 key（数值型）"),
    template_id: int | None = Query(None, description="表单模板 id；不传则跨模板取该 field_key 的全部记录"),
    subgroup_size: int = Query(5, ge=2, le=10, description="子组大小（系数表支持 2..10）"),
    limit: int = Query(25, ge=1, le=500, description="子组数量上限（取最近 limit*subgroup_size 条记录）"),
    equipment_id: int | None = Query(None, description="按机台过滤"),
    only_audited: bool = Query(True, description="仅取已审核记录（status=已审核 或 audited=True）"),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """生成 Xbar-R 控制图及过程能力指数 Cp/Cpk。"""
    return get_spc_chart(
        db,
        template_id=template_id,
        field_key=field_key,
        subgroup_size=subgroup_size,
        limit=limit,
        equipment_id=equipment_id,
        only_audited=only_audited,
    )


@router.get("/fields", response_model=list[dict], dependencies=[Depends(require_permission("production.spc_view"))])
def list_numeric_fields_api(
    template_id: int = Query(..., description="表单模板 id"),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    """返回某模板 field_schema 中 type=number 的字段（key/label/unit/min/max）。"""
    return list_numeric_fields(db, template_id=template_id)
