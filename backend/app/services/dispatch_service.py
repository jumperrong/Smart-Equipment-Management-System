from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import (
    Dispatch, DispatchStatus, ProductionOrder, ProductionOrderStatus,
    Equipment, EquipmentStatus, WorkOrder, WorkOrderStatus,
    ProcessSection, RoutingStep, Routing, FormTemplate,
    FormRecord, FormRecordValue, User, UserRole,
)
from app.schemas import DispatchCreate, DispatchUpdate


VALID_DISPATCH_TRANSITIONS = {
    ("QUEUED", "ASSIGNED"), ("QUEUED", "CANCELLED"),
    ("ASSIGNED", "RUNNING"), ("ASSIGNED", "QUEUED"), ("ASSIGNED", "CANCELLED"),
    ("RUNNING", "COMPLETED"), ("RUNNING", "HELD"), ("RUNNING", "SCRAPPED"),
    ("HELD", "RUNNING"), ("HELD", "CANCELLED"),
    ("COMPLETED", "RUNNING"),  # 允许退回
}


def _resolve_form_template_id(db: Session, obj_in: DispatchCreate, mo: ProductionOrder) -> int | None:
    """解析派工应采用的工艺数据字段模板 id。

    优先级：
    1) obj_in.process_section_id 指定的工段关联的 form_template_id
    2) 否则按 mo.routing_id + step_seq 找 RoutingStep，从其 process_section_id 或 param_form_template_id 读取
    3) 找不到则返回 None（派工不强制要求工艺数据采集）
    """
    # 1) 入参显式指定的工段
    section_id = getattr(obj_in, "process_section_id", None)
    if section_id:
        s = db.query(ProcessSection).filter(ProcessSection.id == section_id).first()
        if s and s.form_template_id:
            return s.form_template_id

    # 2) 通过 MO 的路由版本找 RoutingStep
    if mo.routing_id:
        step = db.query(RoutingStep).filter(
            RoutingStep.routing_id == mo.routing_id,
            RoutingStep.seq == obj_in.step_seq,
        ).first()
        if step:
            # 2a) 步骤引用了工段，从工段读取
            if step.process_section_id:
                ps = db.query(ProcessSection).filter(ProcessSection.id == step.process_section_id).first()
                if ps and ps.form_template_id:
                    return ps.form_template_id
            # 2b) 步骤直接挂接了 form_template_id
            if step.param_form_template_id:
                return step.param_form_template_id
    return None


def _init_form_record_for_dispatch(
    db: Session,
    dispatch: Dispatch,
    form_template_id: int,
    operator_id: int | None,
    operator_name: str | None,
) -> FormRecord:
    """按模板初始化一份草稿工艺数据 FormRecord，绑定到派工。

    - 字段值按模板 default_value 预填
    - 标题自动生成：派工单号 + 工序名
    - 不联动 ProcessDocument（派工场景不需要文件库条目；如需后续可在前端补创建）
    - 模板停用/字段缺失时不阻断派工，仅跳过初始化
    """
    tpl = db.query(FormTemplate).filter(FormTemplate.id == form_template_id).first()
    if not tpl:
        raise HTTPException(500, f"工段引用的表单模板 id={form_template_id} 不存在，数据损坏")
    if not tpl.is_active:
        # 模板停用：不阻断派工，仅不初始化
        return None

    # 兜底规范化字段定义
    from app.services.form_template_service import (
        sorted_fields_from_template, auto_generate_record_title,
    )
    fields = sorted_fields_from_template(tpl)

    # 自动生成标题：派工#id · 工序名
    title_parts = [f"派工#{dispatch.id}"]
    if dispatch.step_name:
        title_parts.append(dispatch.step_name)
    if tpl.name:
        title_parts.append(tpl.name)
    title = " · ".join(title_parts)

    record = FormRecord(
        template_id=tpl.id,
        title=title,
        equipment_id=dispatch.equipment_id,
        batch_no=None,
        shift=None,
        production_date=None,
        remark=f"派工单自动初始化 · 操作员={operator_name or '未指定'}",
        status="草稿",
        filled_by=operator_id,
        submitted_at=None,
    )
    db.add(record)
    db.flush()  # 拿到 record.id

    # 按模板 default_value 预填空字段（用户后续在前端填写实际值）
    for f in fields:
        key = f.get("key")
        if not key:
            continue
        v = FormRecordValue(
            record_id=record.id,
            field_key=key,
            field_label_snapshot=f.get("label") or key,
            field_value=f.get("default_value"),
        )
        db.add(v)
    return record


def list_dispatches(db: Session, mo_id: int | None = None, equipment_id: int | None = None, status: str | None = None, operator_id: int | None = None, skip: int = 0, limit: int = 50):
    q = db.query(Dispatch)
    if mo_id:
        q = q.filter(Dispatch.mo_id == mo_id)
    if equipment_id:
        q = q.filter(Dispatch.equipment_id == equipment_id)
    if status:
        q = q.filter(Dispatch.status == status)
    if operator_id:
        q = q.filter(Dispatch.assigned_operator_id == operator_id)
    return q.order_by(Dispatch.id.desc()).offset(skip).limit(limit).all()


def get_dispatch(db: Session, dispatch_id: int) -> Dispatch:
    d = db.query(Dispatch).filter(Dispatch.id == dispatch_id).first()
    if not d:
        raise HTTPException(404, "派工单不存在")
    return d


def create_dispatch(
    db: Session,
    obj_in: DispatchCreate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> Dispatch:
    mo = db.query(ProductionOrder).filter(ProductionOrder.id == obj_in.mo_id).first()
    if not mo:
        raise HTTPException(404, "生产订单不存在")
    if mo.status == ProductionOrderStatus.DRAFT.value:
        raise HTTPException(400, "草稿状态的生产订单不可派工")

    # 校验工段存在（若入参指定了工段）
    section_id = getattr(obj_in, "process_section_id", None)
    if section_id:
        s = db.query(ProcessSection).filter(ProcessSection.id == section_id).first()
        if not s:
            raise HTTPException(404, f"工段 id={section_id} 不存在")

    d = Dispatch(
        mo_id=obj_in.mo_id,
        step_seq=obj_in.step_seq,
        step_name=obj_in.step_name,
        process_section_id=section_id,
        equipment_id=obj_in.equipment_id,
        assigned_operator_id=obj_in.assigned_operator_id,
        assigned_team=obj_in.assigned_team,
        dispatch_qty=obj_in.dispatch_qty,
        planned_start=obj_in.planned_start,
        planned_end=obj_in.planned_end,
        remark=obj_in.remark,
    )
    db.add(d)
    db.flush()  # 拿到 d.id

    # 解析应采用的工艺数据字段模板
    form_template_id = _resolve_form_template_id(db, obj_in, mo)
    if form_template_id:
        record = _init_form_record_for_dispatch(
            db, d, form_template_id, user_id, user_name
        )
        if record is not None:
            d.form_template_id = form_template_id
            d.form_record_id = record.id

    db.commit()
    db.refresh(d)
    return d


def update_dispatch(db: Session, dispatch: Dispatch, obj_in: DispatchUpdate) -> Dispatch:
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    new_status = data.get("status")
    if new_status and dispatch.status and dispatch.status != new_status:
        old_status = dispatch.status if isinstance(dispatch.status, str) else dispatch.status.value
        # 显式校验状态机：所有合法转换（含 CANCELLED）已登记在 VALID_DISPATCH_TRANSITIONS
        if (old_status, new_status) not in VALID_DISPATCH_TRANSITIONS:
            raise HTTPException(400, f"派工状态不允许从 {old_status} 跳转到 {new_status}")
        if new_status == DispatchStatus.RUNNING.value and not dispatch.actual_start:
            data["actual_start"] = datetime.utcnow()
            # MO自动开工：仅当 MO 处于 RELEASED 状态（已下发）时联动
            mo = dispatch.production_order
            if not mo:
                raise HTTPException(400, "派工关联的生产订单不存在，无法开工")
            if mo.status not in (ProductionOrderStatus.RELEASED.value, ProductionOrderStatus.IN_PROGRESS.value):
                raise HTTPException(400, f"生产订单状态为 {mo.status}，不可开工派工（须先下发）")
            if mo.status == ProductionOrderStatus.RELEASED.value:
                mo.status = ProductionOrderStatus.IN_PROGRESS.value
                mo.actual_start = datetime.utcnow()
            # ---- Poka-Yoka 工艺防呆校验 ----
            _poka_yoka_check(db, dispatch, mo)
        if new_status == DispatchStatus.COMPLETED.value and not dispatch.actual_end:
            data["actual_end"] = datetime.utcnow()
        if new_status == DispatchStatus.HELD.value and not dispatch.held_reason:
            data["held_reason"] = data.get("held_reason", "未指定")
    for k, v in data.items():
        setattr(dispatch, k, v)
    db.commit()
    db.refresh(dispatch)
    return dispatch


def hold_dispatch_by_equipment_down(db: Session, equipment_id: int, work_order_id: int | None = None):
    """设备DOWN时自动暂停该设备上所有RUNNING的派工（联动钩子1）"""
    running_dispatches = db.query(Dispatch).filter(
        Dispatch.equipment_id == equipment_id,
        Dispatch.status == DispatchStatus.RUNNING.value,
    ).all()
    for d in running_dispatches:
        d.status = DispatchStatus.HELD.value
        d.held_reason = f"设备DOWN机-关联工单#{work_order_id}" if work_order_id else "设备DOWN机"
        d.held_work_order_id = work_order_id
    if running_dispatches:
        db.flush()
    return len(running_dispatches)


def delete_dispatch(db: Session, dispatch: Dispatch):
    """删除派工：仅允许删除未开工的派工（QUEUED/ASSIGNED）。

    - 已 RUNNING/HELD/COMPLETED/SCRAPPED 的派工不可删，应走取消/完工流程
    - 关联的自动初始化 FormRecord 一并删除（cascade 由 ORM 配置决定，此处显式清理更稳）
    """
    if dispatch.status not in (DispatchStatus.QUEUED.value, DispatchStatus.ASSIGNED.value):
        raise HTTPException(
            400,
            f"派工状态为 {dispatch.status}，不可删除（仅 QUEUED/ASSIGNED 可删，其他状态请走取消流程）",
        )
    # 关联的报工记录若存在则禁止删除（应先删报工）
    if dispatch.labor_reports:
        raise HTTPException(400, "派工存在报工记录，请先删除相关报工后再删除派工")
    db.delete(dispatch)
    db.commit()


# ============ Poka-Yoka 工艺防呆校验 ============

def _poka_yoka_check(db: Session, dispatch: Dispatch, mo: ProductionOrder):
    """派工开工前的防呆校验。任一失败即抛 HTTPException(400)。

    校验项：
    1. 设备状态校验：派工绑定设备时，设备必须为 RUN/IDLE（不允许 DOWN/PM/OFFLINE）
    2. 操作员资质校验：派工有 assigned_operator 时，校验其角色是否符合工段 required_skill_level
    3. 前道工序完工校验：mo.routing 存在时，要求 step_seq 之前的所有工序均有 COMPLETED 派工
    4. 工段启用校验：派工 process_section_id 必须处于启用状态
    5. FormRecord 已初始化：若工段定义了 form_template，派工必须有 form_record_id
    """
    errors = []

    # 1. 设备状态校验
    if dispatch.equipment_id:
        eq = db.query(Equipment).filter(Equipment.id == dispatch.equipment_id).first()
        if eq:
            bad_states = {
                EquipmentStatus.DOWN.value,
                EquipmentStatus.PM.value,
                EquipmentStatus.OFFLINE.value,
            }
            # current_status 用 SAEnum 存储，可能为枚举实例或字符串，统一取 .value 归一化
            cur = eq.current_status
            cur_val = cur.value if isinstance(cur, EquipmentStatus) else cur
            if cur_val in bad_states:
                errors.append(
                    f"设备 {eq.name or eq.asset_no} 状态为 {cur_val}，不可开工派工"
                    f"（须为 RUN/IDLE，DOWN/PM/OFFLINE 需先恢复或换设备）"
                )

    # 2. 操作员资质校验
    if dispatch.assigned_operator_id:
        op = db.query(User).filter(User.id == dispatch.assigned_operator_id).first()
        if op:
            # 取工段定义的 required_skill_level
            req_level = None
            if dispatch.process_section_id:
                sec = db.query(ProcessSection).filter(ProcessSection.id == dispatch.process_section_id).first()
                if sec:
                    req_level = sec.required_skill_level
            if req_level:
                # 角色映射：required_skill_level 字符串 -> 对应 UserRole
                level_to_roles = {
                    "操作员": {UserRole.OPERATOR.value, UserRole.TEAM_LEADER.value, UserRole.ENGINEER.value, UserRole.PROCESS_ENGINEER.value, UserRole.ADMIN.value},
                    "工艺员": {UserRole.PROCESS_ENGINEER.value, UserRole.ENGINEER.value, UserRole.ADMIN.value},
                    "工程师": {UserRole.ENGINEER.value, UserRole.PROCESS_ENGINEER.value, UserRole.ADMIN.value},
                    "L2": {UserRole.TEAM_LEADER.value, UserRole.ENGINEER.value, UserRole.PROCESS_ENGINEER.value, UserRole.ADMIN.value},
                    "L3": {UserRole.ENGINEER.value, UserRole.PROCESS_ENGINEER.value, UserRole.ADMIN.value},
                }
                allowed = level_to_roles.get(req_level)
                if allowed and op.role not in allowed:
                    errors.append(
                        f"操作员 {op.username}（角色 {op.role}）资质不满足工段要求 {req_level}"
                    )

    # 3. 前道工序完工校验
    if mo.routing_id:
        prev_steps = (
            db.query(RoutingStep)
            .filter(
                RoutingStep.routing_id == mo.routing_id,
                RoutingStep.seq < dispatch.step_seq,
            )
            .order_by(RoutingStep.seq)
            .all()
        )
        if prev_steps:
            prev_seqs = [s.seq for s in prev_steps]
            # 查找同 MO 下、step_seq < 当前 的所有派工，要求均已 COMPLETED/SCRAPPED
            prev_dispatches = (
                db.query(Dispatch)
                .filter(
                    Dispatch.mo_id == mo.id,
                    Dispatch.step_seq.in_(prev_seqs),
                )
                .all()
            )
            # 按工序序号分组，每个工序至少有一个 COMPLETED/SCRAPPED 派工
            by_seq: dict[int, list[Dispatch]] = {}
            for d in prev_dispatches:
                by_seq.setdefault(d.step_seq, []).append(d)
            for s in prev_steps:
                ds = by_seq.get(s.seq, [])
                finished = [d for d in ds if d.status in (DispatchStatus.COMPLETED.value, DispatchStatus.SCRAPPED.value)]
                if not finished:
                    errors.append(
                        f"前道工序 #{s.seq} {s.step_name} 尚无完工派工（COMPLETED/SCRAPPED），不可开工本工序"
                    )

    # 4. 工段启用校验
    if dispatch.process_section_id:
        sec = db.query(ProcessSection).filter(ProcessSection.id == dispatch.process_section_id).first()
        if sec and not sec.is_active:
            errors.append(f"工段 {sec.name} 已停用，不可开工（请切换启用工段或联系工艺员启用）")

    # 5. FormRecord 已初始化（仅工段定义了 form_template 时强制）
    if dispatch.process_section_id:
        sec = db.query(ProcessSection).filter(ProcessSection.id == dispatch.process_section_id).first()
        if sec and sec.form_template_id and not dispatch.form_record_id:
            errors.append(
                f"工段 {sec.name} 已绑定工艺数据模板 #{sec.form_template_id}，但派工未初始化表单，"
                f"请重新派工或联系工艺员补建 FormRecord"
            )

    # 6. 首件检验 FAI 校验
    #    若该派工被标记为首件派工（dispatch.is_fai=true），且已提交但未 APPROVED，则拦截
    #    若派工 is_fai=true 且不存在任何 FAI 记录，也拦截
    is_fai = bool(dispatch.is_fai)
    if is_fai:
        from app.models import FirstArticleInspection, FAIStatus
        fai = (
            db.query(FirstArticleInspection)
            .filter(FirstArticleInspection.dispatch_id == dispatch.id)
            .order_by(FirstArticleInspection.id.desc())
            .first()
        )
        if not fai:
            errors.append("该派工为首件派工(is_fai=true)，尚未创建首件检验单(FAI)，不可开工")
        elif fai.status == FAIStatus.APPROVED.value:
            pass  # 已 QA 签核，放行
        elif fai.status == FAIStatus.REJECTED.value:
            errors.append(
                f"首件检验单 {fai.fai_no} 已被 QA 驳回(REJECTED)（原因：{fai.reject_reason or '未填写'}），"
                f"需返工/重做并重新走 FAI 流程后才能批量开工"
            )
        else:
            errors.append(
                f"首件检验单 {fai.fai_no} 状态为 {fai.status}，必须 QA 签核 APPROVED 后才能批量开工"
            )

    # 7. 物料齐套 Kit Check 校验
    #    若派工存在物料清单项(MaterialKitItem)，则要求所有项 is_kitted=true
    #    无清单时不拦截（视为不强制齐套检查）
    from app.models import MaterialKitItem
    kit_items = (
        db.query(MaterialKitItem)
        .filter(MaterialKitItem.dispatch_id == dispatch.id)
        .all()
    )
    if kit_items:
        short = [it for it in kit_items if not it.is_kitted]
        if short:
            shortage_desc = "、".join(
                f"{it.material_name}(缺口{max(0,(it.required_qty or 0)-(it.available_qty or 0))}{it.unit or ''})"
                for it in short[:5]
            )
            extra = "" if len(short) <= 5 else f" 等共{len(short)}项"
            errors.append(f"物料未齐套：{shortage_desc}{extra}（请仓管确认齐套后再开工）")

    if errors:
        raise HTTPException(
            400,
            "Poka-Yoka 防呆校验未通过：" + " | ".join(errors),
        )



