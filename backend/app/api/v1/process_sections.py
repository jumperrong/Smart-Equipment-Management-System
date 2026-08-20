"""工段库 API：管理员维护可复用工艺单元，绑定设备组与工艺数据采集模板。

工段库与生产订单/工序路由分离，作为"产品在某设备进行某工艺需采集哪些数据"的
可复用模板源。创建工序路由时可引用工段快速填充，派工时按工段关联的 FormTemplate
自动初始化空白工艺数据表单供操作员填写。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import ProcessSectionCreate, ProcessSectionUpdate, ProcessSectionOut
from app.services.process_section_service import (
    list_process_sections,
    get_process_section,
    create_process_section,
    update_process_section,
    delete_process_section,
    get_section_form_template_name,
)

router = APIRouter(prefix="/process-sections", tags=["工段库"])


def _to_out(db: Session, section) -> ProcessSectionOut:
    """ORM → ProcessSectionOut，补展示辅助字段。"""
    out = ProcessSectionOut.model_validate(section)
    out.form_template_name = get_section_form_template_name(db, section)
    return out


@router.get("", response_model=list[ProcessSectionOut])
def list_process_sections_api(
    equipment_group: str | None = Query(None, description="按设备组过滤"),
    is_active: bool | None = Query(None, description="按启用状态过滤"),
    keyword: str | None = Query(None, description="按名称/编码/说明模糊搜索"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    items = list_process_sections(
        db,
        equipment_group=equipment_group,
        is_active=is_active,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return [_to_out(db, s) for s in items]


@router.get("/{section_id}", response_model=ProcessSectionOut)
def get_process_section_api(section_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    s = get_process_section(db, section_id)
    return _to_out(db, s)


@router.post("", response_model=ProcessSectionOut, dependencies=[Depends(require_permission("production.section_write"))])
def create_process_section_api(obj_in: ProcessSectionCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    s = create_process_section(db, obj_in, cu.id, cu.username)
    return _to_out(db, s)


@router.put("/{section_id}", response_model=ProcessSectionOut, dependencies=[Depends(require_permission("production.section_write"))])
def update_process_section_api(section_id: int, obj_in: ProcessSectionUpdate, db: Session = Depends(get_db)):
    s = get_process_section(db, section_id)
    s = update_process_section(db, s, obj_in)
    return _to_out(db, s)


@router.delete("/{section_id}", dependencies=[Depends(require_permission("production.section_delete"))])
def delete_process_section_api(section_id: int, db: Session = Depends(get_db)):
    s = get_process_section(db, section_id)
    delete_process_section(db, s)
    return {"detail": "已删除"}
