"""工段库服务层。

工段是管理员维护的可复用工艺单元：绑定到设备组（模板层），关联一个 FormTemplate
定义工艺数据采集字段。生产人员派工时可指定在组内某台具体设备上执行（执行层）。

设计要点：
- 工段可被多个产品的 RoutingStep 引用，引用关系独立维护，删除工段前需校验引用
- 关联的 FormTemplate 控制工艺数据采集字段；模板停用/删除由 FormTemplate 域负责
- is_active=False 仅为停用，不阻断引用追溯
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ProcessSection, RoutingStep, Dispatch, FormTemplate
from app.schemas import ProcessSectionCreate, ProcessSectionUpdate


def get_section_form_template_name(db: Session, section: ProcessSection) -> Optional[str]:
    """查工段关联的表单模板名（仅供展示）。"""
    if not section.form_template_id:
        return None
    tpl = db.query(FormTemplate).filter(FormTemplate.id == section.form_template_id).first()
    return tpl.name if tpl else None


def list_process_sections(
    db: Session,
    equipment_group: Optional[str] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    q = db.query(ProcessSection)
    if equipment_group:
        q = q.filter(ProcessSection.equipment_group == equipment_group)
    if is_active is not None:
        q = q.filter(ProcessSection.is_active == is_active)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (ProcessSection.name.ilike(kw))
            | (ProcessSection.code.ilike(kw))
            | (ProcessSection.description.ilike(kw))
        )
    return q.order_by(ProcessSection.id.desc()).offset(skip).limit(limit).all()


def get_process_section(db: Session, section_id: int) -> ProcessSection:
    s = db.query(ProcessSection).filter(ProcessSection.id == section_id).first()
    if not s:
        raise HTTPException(404, "工段不存在")
    return s


def create_process_section(
    db: Session,
    obj_in: ProcessSectionCreate,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
) -> ProcessSection:
    # code 唯一性校验
    if obj_in.code:
        existing = db.query(ProcessSection).filter(ProcessSection.code == obj_in.code).first()
        if existing:
            raise HTTPException(400, f"工段编码[{obj_in.code}]已存在")
    # 关联模板存在性校验
    if obj_in.form_template_id:
        tpl = db.query(FormTemplate).filter(FormTemplate.id == obj_in.form_template_id).first()
        if not tpl:
            raise HTTPException(404, f"表单模板 id={obj_in.form_template_id} 不存在")

    s = ProcessSection(
        name=obj_in.name,
        code=obj_in.code,
        equipment_group=obj_in.equipment_group,
        form_template_id=obj_in.form_template_id,
        standard_cycle_min=obj_in.standard_cycle_min,
        theoretical_uph=obj_in.theoretical_uph,
        required_skill_level=obj_in.required_skill_level,
        acceptance_criteria=obj_in.acceptance_criteria,
        sop_doc_id=obj_in.sop_doc_id,
        description=obj_in.description,
        is_active=obj_in.is_active,
        created_by_id=user_id,
        created_by_name=user_name,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def update_process_section(
    db: Session,
    section: ProcessSection,
    obj_in: ProcessSectionUpdate,
) -> ProcessSection:
    data = obj_in.model_dump(exclude_unset=True)

    # code 唯一性校验（若改动）
    if "code" in data and data["code"]:
        new_code = data["code"]
        if new_code != section.code:
            existing = db.query(ProcessSection).filter(
                ProcessSection.code == new_code,
                ProcessSection.id != section.id,
            ).first()
            if existing:
                raise HTTPException(400, f"工段编码[{new_code}]已存在")

    # 关联模板存在性校验
    if "form_template_id" in data and data["form_template_id"]:
        tpl = db.query(FormTemplate).filter(FormTemplate.id == data["form_template_id"]).first()
        if not tpl:
            raise HTTPException(404, f"表单模板 id={data['form_template_id']} 不存在")

    for k, v in data.items():
        setattr(section, k, v)
    section.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(section)
    return section


def delete_process_section(db: Session, section: ProcessSection):
    """硬删除前校验引用：被 RoutingStep 或 Dispatch 引用时禁止删除。

    若只是想停用，应使用 PUT 将 is_active=False。
    """
    routing_refs = db.query(RoutingStep).filter(
        RoutingStep.process_section_id == section.id
    ).count()
    if routing_refs:
        raise HTTPException(
            400,
            f"工段被 {routing_refs} 处工序步骤引用，不能删除；请改为停用（is_active=false）或先解除引用",
        )
    dispatch_refs = db.query(Dispatch).filter(
        Dispatch.process_section_id == section.id
    ).count()
    if dispatch_refs:
        raise HTTPException(
            400,
            f"工段被 {dispatch_refs} 处派工引用，不能删除；请改为停用（is_active=false）",
        )
    db.delete(section)
    db.commit()


def apply_section_to_step(step: RoutingStep, section: ProcessSection) -> None:
    """从工段库引用时，把工段字段同步到工序步骤（仅填充步骤上未显式赋值的字段）。

    由调用方决定是否调用：Routing 服务在创建/更新 step 时若收到 process_section_id
    可触发此同步，便于步骤保留可读快照（即使工段后续被改动也能追溯历史工艺参数）。
    """
    if not step.standard_cycle_min and section.standard_cycle_min:
        step.standard_cycle_min = section.standard_cycle_min
    if not step.theoretical_uph and section.theoretical_uph:
        step.theoretical_uph = section.theoretical_uph
    if not step.required_skill_level and section.required_skill_level:
        step.required_skill_level = section.required_skill_level
    if not step.acceptance_criteria and section.acceptance_criteria:
        step.acceptance_criteria = section.acceptance_criteria
    if not step.sop_doc_id and section.sop_doc_id:
        step.sop_doc_id = section.sop_doc_id
    if not step.equipment_group and section.equipment_group:
        step.equipment_group = section.equipment_group
    if not step.param_form_template_id and section.form_template_id:
        step.param_form_template_id = section.form_template_id
