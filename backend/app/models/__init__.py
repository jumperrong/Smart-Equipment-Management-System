from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Enum as SAEnum,
    Float, JSON, Numeric, UniqueConstraint, Index, text,
)
from sqlalchemy.orm import relationship
from enum import Enum

from app.core.database import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    PROCESS_ENGINEER = "process_engineer"
    QA = "qa"
    OPERATOR = "operator"
    VIEWER = "viewer"


class EquipmentStatus(str, Enum):
    RUN = "RUN"
    IDLE = "IDLE"
    DOWN = "DOWN"
    PM = "PM"
    ENGINEERING = "ENGINEERING"
    PROCESS_VALIDATION = "PROCESS_VALIDATION"  # 工艺验证
    OTHER = "OTHER"  # 其他（需输入说明）
    OFFLINE = "OFFLINE"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    full_name = Column(String(128), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # 登录失败计数 / 账户临时锁定
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True, comment="账户锁定截止时间")
    # 强制首次登录改密 / 上次改密时间
    must_change_password = Column(Boolean, default=False, nullable=False)
    last_password_changed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    status_logs = relationship("EquipmentStatusLog", back_populates="operator")
    inspection_records = relationship("InspectionRecord", back_populates="inspector")
    work_orders = relationship("WorkOrder", back_populates="assignee", foreign_keys="WorkOrder.assignee_id")
    reports = relationship("RepairReport", back_populates="reporter")
    qualifications = relationship("Qualification", back_populates="user")
    training_attendees = relationship("TrainingAttendee", back_populates="user")


class Equipment(Base):
    __tablename__ = "equipments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    asset_no = Column(String(64), unique=True, index=True)
    factory = Column(String(64), nullable=True, comment="厂区")
    area = Column(String(64), nullable=True, comment="区域")
    model = Column(String(128), nullable=True, comment="机型")
    vendor = Column(String(128), nullable=True, comment="供应商")
    serial_no = Column(String(128), nullable=True, comment="序列号")
    install_date = Column(DateTime, nullable=True)
    theoretical_cycle = Column(Float, nullable=True, comment="理论节拍(秒/片)")
    spec = Column(JSON, default=dict, nullable=True, comment="规格参数JSON")
    description = Column(Text, nullable=True)
    current_status = Column(SAEnum(EquipmentStatus), default=EquipmentStatus.OFFLINE)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    status_logs = relationship("EquipmentStatusLog", back_populates="equipment", cascade="all, delete-orphan")
    attachments = relationship("EquipmentAttachment", back_populates="equipment", cascade="all, delete-orphan")
    process_documents = relationship("ProcessDocument", back_populates="equipment", cascade="all, delete-orphan")
    spare_parts = relationship("EquipmentSparePart", back_populates="equipment", cascade="all, delete-orphan")
    inspection_templates = relationship("InspectionTemplate", back_populates="equipment")
    work_orders = relationship("WorkOrder", back_populates="equipment")
    reports = relationship("RepairReport", back_populates="equipment")
    pm_plans = relationship("PMPlan", back_populates="equipment")
    d8_reports = relationship("D8Report", back_populates="equipment")
    fmeas = relationship("FMEA", back_populates="equipment")
    qualifications = relationship("Qualification", back_populates="equipment")
    trainings = relationship("Training", back_populates="equipment")
    asset_applications = relationship("AssetApplication", back_populates="equipment")
    asset_inventory_lines = relationship("AssetInventoryLine", back_populates="equipment")
    production_records = relationship("ProductionRecord", back_populates="equipment")


class EquipmentStatusLog(Base):
    __tablename__ = "equipment_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    from_status = Column(SAEnum(EquipmentStatus), nullable=True)
    to_status = Column(SAEnum(EquipmentStatus), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True, comment="持续时长(分钟)")
    reason_code = Column(String(64), nullable=True, comment="原因码/分类")
    reason_detail = Column(String(255), nullable=True, comment="详细原因")
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="status_logs")
    operator = relationship("User", back_populates="status_logs")


# ============ 模块 A: 设备档案增强 ============

class EquipmentAttachment(Base):
    __tablename__ = "equipment_attachments"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False, comment="原始文件名")
    stored_path = Column(String(512), nullable=False, comment="存储路径")
    file_size = Column(Integer, nullable=True, comment="字节")
    file_type = Column(String(64), nullable=True, comment="MIME类型")
    category = Column(String(64), nullable=True, comment="分类: SOP/说明书/图纸/其他")
    description = Column(String(255), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="attachments")


# ============ 模块 D: 备件管理 ============

class SparePart(Base):
    __tablename__ = "spare_parts"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(64), unique=True, index=True, nullable=False, comment="备件编号")
    name = Column(String(128), nullable=False, comment="名称")
    spec = Column(String(255), nullable=True, comment="规格型号")
    brand = Column(String(128), nullable=True, comment="品牌")
    unit = Column(String(32), default="个", comment="单位")
    safety_stock = Column(Integer, default=0, comment="安全库存")
    current_stock = Column(Integer, default=0, comment="当前库存")
    unit_price = Column(Float, default=0, nullable=False, comment="单价(元)")
    location = Column(String(128), nullable=True, comment="库位")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = relationship("SparePartMovement", back_populates="spare_part", cascade="all, delete-orphan")
    usages = relationship("SparePartUsage", back_populates="spare_part")
    equipments = relationship("EquipmentSparePart", back_populates="spare_part")


class EquipmentSparePart(Base):
    """设备-易损件关联（一机一档中的易损件清单）"""
    __tablename__ = "equipment_spare_parts"
    __table_args__ = (UniqueConstraint("equipment_id", "spare_part_id", name="uq_eq_sp"),)

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    spare_part_id = Column(Integer, ForeignKey("spare_parts.id"), nullable=False, index=True)
    qty_per = Column(Integer, default=1, comment="单台用量")
    remark = Column(String(255), nullable=True)

    equipment = relationship("Equipment", back_populates="spare_parts")
    spare_part = relationship("SparePart", back_populates="equipments")


class SparePartMovement(Base):
    """出入库记录"""
    __tablename__ = "spare_part_movements"

    id = Column(Integer, primary_key=True, index=True)
    spare_part_id = Column(Integer, ForeignKey("spare_parts.id"), nullable=False, index=True)
    movement_type = Column(String(16), nullable=False, comment="IN入库/OUT出库/ADJUST调整")
    qty = Column(Integer, nullable=False, comment="数量(正数)")
    before_stock = Column(Integer, nullable=True)
    after_stock = Column(Integer, nullable=True)
    ref_type = Column(String(32), nullable=True, comment="来源类型: WORK_ORDER/MANUAL/INIT")
    ref_id = Column(Integer, nullable=True, comment="来源ID")
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    spare_part = relationship("SparePart", back_populates="movements")


class SparePartUsage(Base):
    """工单领用备件"""
    __tablename__ = "spare_part_usages"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    spare_part_id = Column(Integer, ForeignKey("spare_parts.id"), nullable=False, index=True)
    qty = Column(Integer, nullable=False, default=1)
    movement_id = Column(Integer, ForeignKey("spare_part_movements.id"), nullable=True, comment="关联出库记录")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    work_order = relationship("WorkOrder", back_populates="spare_usages")
    spare_part = relationship("SparePart", back_populates="usages")


# ============ 模块 B: 点检与巡检 ============

class InspectionTemplate(Base):
    """点检模板（按设备）"""
    __tablename__ = "inspection_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True, comment="关联设备(可选)")
    frequency = Column(String(16), default="DAILY", comment="频率: DAILY/WEEKLY/MONTHLY")
    is_active = Column(Boolean, default=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="inspection_templates")
    items = relationship("InspectionItem", back_populates="template", cascade="all, delete-orphan")
    records = relationship("InspectionRecord", back_populates="template")


class InspectionItem(Base):
    """点检项目"""
    __tablename__ = "inspection_items"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("inspection_templates.id"), nullable=False, index=True)
    seq = Column(Integer, default=0, comment="顺序")
    name = Column(String(128), nullable=False, comment="检查项名称")
    standard = Column(String(255), nullable=True, comment="标准/方法")
    required = Column(Boolean, default=True, comment="是否必检")

    template = relationship("InspectionTemplate", back_populates="items")


class InspectionRecord(Base):
    """点检记录"""
    __tablename__ = "inspection_records"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("inspection_templates.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True)
    shift = Column(String(16), nullable=True, comment="班次: A/B/C")
    inspect_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    overall_result = Column(String(16), default="OK", comment="整体结果: OK/NG")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("InspectionTemplate", back_populates="records")
    inspector = relationship("User", back_populates="inspection_records")
    results = relationship("InspectionResult", back_populates="record", cascade="all, delete-orphan")


class InspectionResult(Base):
    """点检逐项结果"""
    __tablename__ = "inspection_results"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("inspection_records.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("inspection_items.id"), nullable=True)
    item_name = Column(String(128), nullable=False, comment="快照: 项目名")
    result = Column(String(16), nullable=False, comment="OK/NG/NA")
    value = Column(String(128), nullable=True, comment="实测值")
    remark = Column(String(255), nullable=True)

    record = relationship("InspectionRecord", back_populates="results")


# ============ 模块 C: 维护管理(PM) + 故障维修 ============

class WorkOrderType(str, Enum):
    PM = "PM"            # 预防性维护
    REPAIR = "REPAIR"    # 故障维修（由 DOWN 触发或手动创建）


class WorkOrderStatus(str, Enum):
    CREATED = "CREATED"        # 已创建
    ASSIGNED = "ASSIGNED"      # 已派工
    IN_PROGRESS = "IN_PROGRESS"  # 执行中
    PENDING_REVIEW = "PENDING_REVIEW"  # 待验收
    COMPLETED = "COMPLETED"    # 已完成
    CANCELLED = "CANCELLED"    # 已取消


class FaultCategory(str, Enum):
    MECHANICAL = "MECHANICAL"  # 机械
    ELECTRICAL = "ELECTRICAL"  # 电气
    PROCESS = "PROCESS"        # 工艺
    SOFTWARE = "SOFTWARE"      # 软件
    CONSUMABLE = "CONSUMABLE"  # 耗材/备件
    OTHER = "OTHER"            # 其他


class PMPlan(Base):
    """预防性维护计划"""
    __tablename__ = "pm_plans"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False, comment="计划名称")
    cycle_days = Column(Integer, nullable=False, comment="周期(天)")
    items = Column(JSON, default=list, comment="维护项目清单")
    next_due_date = Column(DateTime, nullable=True, comment="下次到期")
    planned_start_hour = Column(Integer, default=9, comment="计划开始时段(0-23点)")
    planned_duration_minutes = Column(Integer, default=120, comment="计划持续时长(分钟)")
    is_active = Column(Boolean, default=True)
    last_executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="pm_plans")


class RepairReport(Base):
    """报修单"""
    __tablename__ = "repair_reports"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    phenomenon = Column(Text, nullable=False, comment="故障现象")
    urgency = Column(String(16), default="NORMAL", comment="紧急度: LOW/NORMAL/HIGH/CRITICAL")
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, comment="转工单")
    status = Column(String(16), default="OPEN", comment="OPEN/CONVERTED/CLOSED")
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="reports")
    reporter = relationship("User", back_populates="reports")


class WorkOrder(Base):
    """统一工单（PM 预防性维护 / REPAIR 故障维修）"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), unique=True, index=True, nullable=False, comment="工单号")
    type = Column(SAEnum(WorkOrderType), nullable=False)
    status = Column(SAEnum(WorkOrderStatus), default=WorkOrderStatus.CREATED, nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, comment="标题/概述")
    description = Column(Text, nullable=True, comment="任务描述")
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="负责人")
    source_report_id = Column(Integer, ForeignKey("repair_reports.id"), nullable=True, comment="旧版来源报修单(历史兼容)")
    pm_plan_id = Column(Integer, ForeignKey("pm_plans.id"), nullable=True, comment="来源PM计划")
    status_log_id = Column(Integer, ForeignKey("equipment_status_logs.id"), nullable=True, comment="关联状态日志(触发DOWN的那条)")
    urgency = Column(String(16), default="NORMAL", comment="紧急度: LOW/NORMAL/HIGH/CRITICAL")
    # 故障分析
    fault_category = Column(SAEnum(FaultCategory), nullable=True, comment="故障分类")
    root_cause = Column(Text, nullable=True, comment="根因")
    solution = Column(Text, nullable=True, comment="处置措施")
    prevention = Column(Text, nullable=True, comment="预防措施")
    # 时间
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    # SLA 字段
    sla_response_minutes = Column(Integer, nullable=True, comment="SLA目标响应时长(分钟)")
    sla_resolution_minutes = Column(Integer, nullable=True, comment="SLA目标解决时长(分钟)")
    actual_response_minutes = Column(Integer, nullable=True, comment="实际响应时长(分钟, 创建到首次受理)")
    actual_resolution_minutes = Column(Integer, nullable=True, comment="实际解决时长(分钟, 创建到关闭)")
    sla_breach = Column(Boolean, default=False, nullable=False, comment="SLA是否违约")
    escalated = Column(Boolean, default=False, nullable=False, comment="是否已升级")
    escalated_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="升级到谁")
    escalated_at = Column(DateTime, nullable=True, comment="升级时间")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="work_orders")
    assignee = relationship("User", back_populates="work_orders", foreign_keys=[assignee_id])
    five_whys = relationship("FiveWhy", back_populates="work_order", cascade="all, delete-orphan")
    spare_usages = relationship("SparePartUsage", back_populates="work_order", cascade="all, delete-orphan")


class FiveWhy(Base):
    """5Why 根因分析记录"""
    __tablename__ = "five_whys"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False, comment="第几问: 1-5")
    question = Column(Text, nullable=False, comment="为什么...")
    answer = Column(Text, nullable=True, comment="原因")
    created_at = Column(DateTime, default=datetime.utcnow)

    work_order = relationship("WorkOrder", back_populates="five_whys")


# ============ 模块 E: 品管工具 (8D / FMEA) ============

class D8Status(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class D8Report(Base):
    """8D 报告"""
    __tablename__ = "d8_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_no = Column(String(32), unique=True, index=True, nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, comment="关联工单")
    title = Column(String(255), nullable=False)
    problem = Column(Text, nullable=True, comment="D0 问题描述")
    d1_team = Column(Text, nullable=True, comment="D1 团队")
    d2_problem_desc = Column(Text, nullable=True, comment="D2 问题定义")
    d3_interim = Column(Text, nullable=True, comment="D3 临时围堵措施")
    d4_root_cause = Column(Text, nullable=True, comment="D4 根本原因")
    d5_permanent = Column(Text, nullable=True, comment="D5 永久纠正措施")
    d6_implement = Column(Text, nullable=True, comment="D6 措施实施与验证")
    d7_prevent = Column(Text, nullable=True, comment="D7 预防再发生")
    d8_recognition = Column(Text, nullable=True, comment="D8 团队致谢")
    status = Column(SAEnum(D8Status), default=D8Status.OPEN, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    equipment = relationship("Equipment", back_populates="d8_reports")


class FMEA(Base):
    """FMEA 失效模式与影响分析"""
    __tablename__ = "fmeas"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    version = Column(String(32), default="1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="fmeas")
    items = relationship("FMEAItem", back_populates="fmea", cascade="all, delete-orphan")


class FMEAItem(Base):
    """FMEA 失效条目"""
    __tablename__ = "fmea_items"

    id = Column(Integer, primary_key=True, index=True)
    fmea_id = Column(Integer, ForeignKey("fmeas.id"), nullable=False, index=True)
    seq = Column(Integer, default=0)
    process_step = Column(String(128), nullable=True, comment="过程/功能")
    failure_mode = Column(String(255), nullable=False, comment="失效模式")
    failure_effect = Column(Text, nullable=True, comment="失效影响")
    cause = Column(Text, nullable=True, comment="失效原因")
    severity = Column(Integer, default=5, comment="严重度 S 1-10")
    occurrence = Column(Integer, default=5, comment="频度 O 1-10")
    detection = Column(Integer, default=5, comment="探测度 D 1-10")
    rpn = Column(Integer, default=125, comment="风险顺序数 RPN=S*O*D")
    recommended_action = Column(Text, nullable=True, comment="建议措施")
    action_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_due_date = Column(DateTime, nullable=True)
    action_status = Column(String(16), default="OPEN", comment="OPEN/IN_PROGRESS/DONE")
    action_result = Column(Text, nullable=True)
    remark = Column(String(255), nullable=True)

    fmea = relationship("FMEA", back_populates="items")


# ============ 模块 F: 环境核查 ============

class EnvironmentLog(Base):
    """洁净与环境参数核查表"""
    __tablename__ = "environment_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_date = Column(DateTime, nullable=False, index=True, comment="核查时间")
    factory = Column(String(64), nullable=True)
    area = Column(String(64), nullable=True, comment="区域")
    shift = Column(String(16), nullable=True)
    temperature = Column(Float, nullable=True, comment="温度℃")
    humidity = Column(Float, nullable=True, comment="湿度%")
    cleanliness = Column(String(32), nullable=True, comment="洁净度等级")
    particles = Column(Float, nullable=True, comment="粒子数")
    pressure = Column(Float, nullable=True, comment="压差Pa")
    result = Column(String(16), default="OK", comment="OK/NG")
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============ 模块 G: 人员资质 / 培训 / 技能矩阵 ============

class SkillLevel(str, Enum):
    PRIMARY = "PRIMARY"        # 主操作
    SECONDARY = "SECONDARY"   # 副操作
    TRAINING = "TRAINING"      # 培训中
    NONE = "NONE"


class Qualification(Base):
    """人员资质考核表 (设备操作授权)"""
    __tablename__ = "qualifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True, comment="null=通用资质")
    skill_level = Column(SAEnum(SkillLevel), default=SkillLevel.TRAINING, nullable=False)
    certified_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    certified_by = Column(String(64), nullable=True, comment="考核人")
    score = Column(Float, nullable=True, comment="考核成绩")
    remark = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="qualifications")
    equipment = relationship("Equipment", back_populates="qualifications")


class Training(Base):
    """培训计划"""
    __tablename__ = "trainings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True)
    trainer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    planned_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String(16), default="PLANNED", comment="PLANNED/IN_PROGRESS/COMPLETED/CANCELLED")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="trainings")
    attendees = relationship("TrainingAttendee", back_populates="training", cascade="all, delete-orphan")


class TrainingAttendee(Base):
    """培训记录 (师带徒)"""
    __tablename__ = "training_attendees"

    id = Column(Integer, primary_key=True, index=True)
    training_id = Column(Integer, ForeignKey("trainings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    attendance = Column(String(16), default="PRESENT", comment="PRESENT/ABSENT")
    score = Column(Float, nullable=True)
    passed = Column(Boolean, default=False)
    remark = Column(String(255), nullable=True)

    training = relationship("Training", back_populates="attendees")
    user = relationship("User", back_populates="training_attendees")


# ============ 模块 H: 资产盘点 / 调拨报废 ============

class InventoryStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class AssetInventory(Base):
    """资产盘点任务"""
    __tablename__ = "asset_inventories"

    id = Column(Integer, primary_key=True, index=True)
    inventory_no = Column(String(32), unique=True, index=True)
    name = Column(String(255), nullable=False)
    plan_date = Column(DateTime, nullable=True)
    status = Column(SAEnum(InventoryStatus), default=InventoryStatus.PLANNED, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lines = relationship("AssetInventoryLine", back_populates="inventory", cascade="all, delete-orphan")


class AssetInventoryLine(Base):
    """盘点明细"""
    __tablename__ = "asset_inventory_lines"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("asset_inventories.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False)
    system_status = Column(String(64), nullable=True, comment="台账状态快照")
    actual_found = Column(Boolean, default=False, comment="现场是否找到")
    location_match = Column(Boolean, default=False, comment="位置是否一致")
    result = Column(String(16), default="PENDING", comment="PENDING/MATCH/MISMATCH/MISSING")
    checked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    checked_at = Column(DateTime, nullable=True)
    remark = Column(String(255), nullable=True)

    inventory = relationship("AssetInventory", back_populates="lines")
    equipment = relationship("Equipment", back_populates="asset_inventory_lines")


class ApplicationType(str, Enum):
    TRANSFER = "TRANSFER"  # 调拨
    SCRAP = "SCRAP"        # 报废


class ApplicationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class AssetApplication(Base):
    """设备调拨/报废申请表"""
    __tablename__ = "asset_applications"

    id = Column(Integer, primary_key=True, index=True)
    application_no = Column(String(32), unique=True, index=True)
    type = Column(SAEnum(ApplicationType), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    from_location = Column(String(128), nullable=True)
    to_location = Column(String(128), nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False)
    applicant_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    remark = Column(String(255), nullable=True)

    equipment = relationship("Equipment", back_populates="asset_applications")


# ============ 模块 I: 产品 / 生产记录 (OEE 支撑) ============

class Product(Base):
    """产品基础信息"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False, comment="产品编号")
    name = Column(String(128), nullable=False, comment="产品名称")
    spec = Column(String(255), nullable=True, comment="规格型号")
    unit = Column(String(32), default="片", comment="单位")
    target_cycle = Column(Float, nullable=True, comment="理论节拍(秒/件)")
    remark = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    production_records = relationship("ProductionRecord", back_populates="product")


class ProductionRecord(Base):
    """生产记录（用于 OEE 计算）"""
    __tablename__ = "production_records"

    id = Column(Integer, primary_key=True, index=True)
    record_no = Column(String(32), unique=True, index=True, nullable=False, comment="记录编号")
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    batch_no = Column(String(64), nullable=True, comment="批次号")
    plan_qty = Column(Integer, default=0, comment="计划投入量")
    input_qty = Column(Integer, default=0, comment="实际投入量")
    good_qty = Column(Integer, default=0, comment="合格数量")
    defect_qty = Column(Integer, default=0, comment="不合格数量")
    start_time = Column(DateTime, nullable=True, comment="生产开始时间")
    end_time = Column(DateTime, nullable=True, comment="生产结束时间")
    duration_minutes = Column(Float, nullable=True, comment="运行时长(分钟)")
    ideal_cycle = Column(Float, nullable=True, comment="理论节拍(秒/件)快照")
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="production_records")
    product = relationship("Product", back_populates="production_records")


# ============ 模块 J: 系统字典/配置 ============

class DictionaryCategory(str, Enum):
    """字典分类"""
    FACTORY = "factory"                 # 厂区
    AREA = "area"                        # 区域
    EQUIPMENT_STATUS = "equipment_status"  # 设备状态
    WORK_ORDER_TYPE = "work_order_type"  # 工单类型
    SPARE_PART_CATEGORY = "spare_part_category"  # 备件分类
    REASON_CODE = "reason_code"          # 状态变更原因
    CUSTOM = "custom"                    # 自定义


class DictionaryItem(Base):
    """系统字典项（管理员可配置的选项值）"""
    __tablename__ = "dictionary_items"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(SAEnum(DictionaryCategory), nullable=False, index=True, comment="字典分类")
    code = Column(String(64), nullable=False, comment="编码(英文/简写)")
    label = Column(String(128), nullable=False, comment="显示名称")
    value = Column(String(128), nullable=True, comment="值(默认等于code)")
    sort_order = Column(Integer, default=0, comment="排序")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_system = Column(Boolean, default=False, nullable=False, comment="系统内置(不可删除)")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dict_category_code", "category", "code", unique=True),
    )


class RolePermission(Base):
    """角色-功能权限映射表。每行记录某角色对某 feature_key 是否放行。

    启动时由 permission_service.seed_default_permissions 把缺失的 (role, feature_key)
    按 constants.DEFAULT_ROLE_MATRIX 补齐。管理员可在前端调整 allowed 值。
    """
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(SAEnum(UserRole), nullable=False, index=True)
    feature_key = Column(String(64), nullable=False, index=True)
    allowed = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("role", "feature_key", name="uq_role_feature"),
    )


class SystemSetting(Base):
    """系统设置项（环境变量可视化编辑）。

    存储管理员通过界面调整的可配置环境变量值。
    修改后由 system_setting_service 写入 .env 文件，重启服务后生效。
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False, comment="环境变量名")
    value = Column(Text, nullable=True, comment="当前设置的值(JSON编码: string/int/float/bool/list)")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class IPWhitelist(Base):
    """IP 白名单。

    - enabled=False 表示禁用白名单(允许所有 IP 访问)
    - 单条记录 ip="*" 表示允许所有；通常配合 enabled=True 起到"开放模式"作用
    - 127.0.0.1 / ::1 永远隐式允许(避免锁死本机)
    """
    __tablename__ = "ip_whitelist"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String(64), unique=True, index=True, nullable=False, comment="IPv4/IPv6 地址或 CIDR")
    label = Column(String(128), nullable=True, comment="备注名")
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IPAccessLog(Base):
    """IP 访问日志。

    - 记录未通过白名单的访问尝试
    - status: PENDING(待审) / APPROVED(已批准,已加入白名单) / REJECTED(已拒绝)
    - 管理员可在界面把 PENDING 的 IP 一键加入白名单
    """
    __tablename__ = "ip_access_logs"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String(64), nullable=False, index=True, comment="访问者 IP")
    path = Column(String(255), nullable=True, comment="请求路径")
    method = Column(String(16), nullable=True, comment="HTTP 方法")
    user_agent = Column(String(512), nullable=True)
    status = Column(String(16), default="PENDING", nullable=False, comment="PENDING/APPROVED/REJECTED")
    attempt_count = Column(Integer, default=1, nullable=False, comment="尝试次数")
    first_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_attempt_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    remark = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_ip_access_logs_ip_status", "ip", "status"),
    )


# ============ 模块 K: 工艺文件 ============

class ProcessDocument(Base):
    """工艺文件（与设备绑定，区别于设备维修保养附件）。

    大类(category)：
    - guide 指导性文件：Recipe 配方、流程图、规格书、作业指导书等（重版本管理）
    - record 作业记录文件：批次记录、参数记录、检验记录、交接班记录等（重批次/班次/日期）
    版本管理：同一份文档可有多个版本，共享 group_id；is_latest=True 表示当前最新版本。
    状态管理：草稿/生效/作废，通过专用状态流转 API 变更，保证流转合法性。
    """
    __tablename__ = "process_documents"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    category = Column(String(16), default="guide", nullable=False, server_default=text("'guide'"), comment="大类: guide指导性/record作业记录")
    doc_no = Column(String(128), nullable=True, index=True, comment="文档编号(用户手动编辑，体系文控用)")
    doc_class = Column(String(16), nullable=True, comment="文控一级分类: SOP/SIP/SPEC/FORM/RECORD/EXTERN")
    doc_name = Column(String(255), nullable=False, comment="文件名称")
    doc_type = Column(String(64), nullable=True, comment="类型: 指导性-Recipe/Flowchart/Spec/其他; 作业记录-BatchRecord/ParamLog/InspectionRecord/ShiftHandover/其他")
    version = Column(String(64), nullable=True, comment="版本号(显示用)")
    version_seq = Column(Integer, default=1, nullable=False, server_default=text("1"), comment="版本序号(同group内递增)")
    group_id = Column(String(64), nullable=False, index=True, server_default=text("''"), comment="版本分组ID(同文档多版本共享)")
    is_latest = Column(Boolean, default=True, nullable=False, server_default=text("1"), comment="是否最新版本")
    status = Column(String(32), default="草稿", nullable=False, comment="草稿/生效/作废")
    effective_date = Column(DateTime, nullable=True, comment="生效日期")
    review_cycle_month = Column(Integer, nullable=True, comment="复审周期(月)；NULL=不需要定期复审")
    next_review_date = Column(DateTime, nullable=True, comment="下次复审日期（生效时按 effective_date+cycle 自动计算）")
    # 作业记录专属字段（指导性文件可为空）
    batch_no = Column(String(64), nullable=True, index=True, comment="作业记录-批号")
    shift = Column(String(16), nullable=True, comment="作业记录-班次: A/B/C")
    production_date = Column(DateTime, nullable=True, comment="作业记录-生产日期")
    stored_path = Column(String(512), nullable=False, comment="存储路径；结构化表单记录此处为 '' 或特殊占位，实际内容在关联 form_record 中")
    file_size = Column(Integer, nullable=True, comment="字节")
    file_type = Column(String(64), nullable=True, comment="MIME类型")
    description = Column(String(500), nullable=True, comment="说明")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    form_record_id = Column(Integer, ForeignKey("form_records.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的结构化表单记录(基于模板生成)")

    # —— 外来文件字段（阶段 3）：doc_class=EXTERN 时使用
    source_type = Column(String(16), nullable=True, comment="来源类型: CUSTOMER客户/HQ总部/REGULATION法规/VENDOR设备商/INTERNAL内部")
    source_ref_no = Column(String(128), nullable=True, comment="外部来源文件编号")
    received_date = Column(DateTime, nullable=True, comment="接收日期")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="process_documents")
    form_record = relationship("FormRecord", back_populates="process_documents")
    approvals = relationship("DocumentApproval", back_populates="process_document", cascade="all, delete-orphan", order_by="DocumentApproval.stage_order.asc(), DocumentApproval.signed_at.asc()")
    change_logs = relationship("DocumentChangeLog", back_populates="process_document", cascade="all, delete-orphan", order_by="DocumentChangeLog.created_at.desc()")
    distributions = relationship("DocumentDistribution", back_populates="process_document", cascade="all, delete-orphan")


# ============ 模块 K2: 文档编号规则（体系文控用） ============
# 管理员在此定义各文控分类（SOP/SIP/SPEC/FORM/RECORD/EXTERN）的编号格式，
# 系统根据规则自动生成文档编号。编号格式：
#   {prefix}[-{year}][-{month}][-{equipment_code}]-{seq:0{seq_width}d}
# 例：SOP-2026-001 / SIP-ET-001 / FORM-B202608-0001

class DocNoRule(Base):
    """文档编号规则（每个文控分类一条）。

    生成编号时从 next_seq 取值并自增；
    编号格式由 prefix / use_year / use_month / use_equipment_code / seq_width 组合决定。
    """
    __tablename__ = "doc_no_rules"

    id = Column(Integer, primary_key=True, index=True)
    doc_class = Column(String(16), unique=True, nullable=False, index=True, comment="文控分类: SOP/SIP/SPEC/FORM/RECORD/EXTERN")
    prefix = Column(String(16), nullable=False, comment="编号前缀，如 SOP/SIP/SPEC")
    use_equipment_code = Column(Boolean, default=False, nullable=False, server_default=text("0"), comment="是否包含机台资产编号")
    use_year = Column(Boolean, default=True, nullable=False, server_default=text("1"), comment="是否包含年份")
    use_month = Column(Boolean, default=False, nullable=False, server_default=text("0"), comment="是否包含月份")
    seq_width = Column(Integer, default=3, nullable=False, comment="流水号位数(3=001, 4=0001)")
    next_seq = Column(Integer, default=1, nullable=False, server_default=text("1"), comment="下一个待分配流水号")
    is_active = Column(Boolean, default=True, nullable=False, server_default=text("1"), index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ 模块 K3: 文档审批链（DocumentApproval）========
# 每条 process_document_version 可有 0~多条审批记录，
# 阶段 stage = 'prepare'（编制签名） / 'review'（审核） / 'approve'（批准）。
# 每个阶段保存：签署人、签署时角色、签署时间、签署时二次密码校验结果、签名 hash。

class DocumentApproval(Base):
    __tablename__ = "document_approvals"

    id = Column(Integer, primary_key=True, index=True)
    process_document_id = Column(Integer, ForeignKey("process_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(16), nullable=False, comment="prepare/review/approve")
    stage_order = Column(Integer, default=1, nullable=False, comment="审批顺序号(1=编制 2=审核 3=批准)")
    result = Column(String(16), nullable=False, comment="approved/rejected")
    comment = Column(String(500), nullable=True)

    signer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signer_username = Column(String(64), nullable=False, comment="快照：签署时用户名")
    signer_display_name = Column(String(64), nullable=True, comment="快照：签署时显示名")
    signer_role = Column(String(32), nullable=True, comment="快照：签署时角色")
    signed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 电子签名指纹：SHA256(doc_id|stage|signer_id|signed_at|comment|password_validated)
    signature = Column(String(128), nullable=False)
    password_validated = Column(Boolean, default=False, nullable=False, comment="签署时是否二次校验密码（体系合规要求=TRUE）")

    process_document = relationship("ProcessDocument", back_populates="approvals")


# ============ 模块 K4: 结构化修订记录 =========
# 每次发布新版本 / 作废 / 上传新版本时，记录逐条变更点。
# 审核员可核对每个变更点的影响评估。

class DocumentChangeLog(Base):
    __tablename__ = "document_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    process_document_id = Column(Integer, ForeignKey("process_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    change_reason = Column(String(32), nullable=False, comment="NEW/REV_VOID/REV_SPEC/REV_STEP/ENG_CHG/QC_NC/CUSTOMER")
    change_summary = Column(String(500), nullable=False, comment="总体变更摘要")
    detail_items_json = Column(JSON, nullable=True, comment="逐行变更项列表：[{seq,change_type:A/M/D,page,before,after,impact}]")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by_username = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    process_document = relationship("ProcessDocument", back_populates="change_logs")


# ============ 模块 K5: 文件分发/作废收回记录 =========
# 电子文件发放给谁（按用户/部门/角色），作废时收回勾选。
# 纸质文件份数统计。

class DocumentDistribution(Base):
    __tablename__ = "document_distributions"

    id = Column(Integer, primary_key=True, index=True)
    process_document_id = Column(Integer, ForeignKey("process_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_type = Column(String(16), nullable=False, comment="USER/ROLE/DEPARTMENT")
    recipient_ref = Column(String(64), nullable=False, comment="用户名/角色名/部门名")
    hold_copies = Column(Integer, default=1, nullable=False, comment="持有份数(电子=1, 纸质可多)")
    medium = Column(String(8), default="E", nullable=False, comment="E=电子 P=纸质")
    issued_at = Column(DateTime, default=datetime.utcnow)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    returned = Column(Boolean, default=False, nullable=False, comment="作废/换新时是否已收回")
    returned_at = Column(DateTime, nullable=True)
    returned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    return_note = Column(String(255), nullable=True)

    process_document = relationship("ProcessDocument", back_populates="distributions")


# ============ 模块 L: 用户自定义表单模板与结构化表单记录 ============
# 场景：工艺记录（批次/参数/检验/交接班）等不再强制要求上传 PDF/Excel，
# 而是：管理员/工艺员先定义 模板 (字段定义 JSON + 可选参考文件)，
# 操作员/工艺员选模板 → 动态渲染表单 → 填写 → 保存为结构化记录(可导出/可展示)。


class FormTemplate(Base):
    """表单模板（字段定义 + 可选参考模板文件）。

    一个模板可被多次使用生成多条 FormRecord（填写值）。
    field_schema 格式（有序 JSON 数组）：
    [
      {
        "key": "bath_no",              // 唯一字段key (建议英文小写+下划线)
        "type": "text",                // text / textarea / number / select / radio / date / datetime / time / boolean
        "label": "批号",                // 显示名
        "required": true,
        "placeholder": "例 B20260801-01",
        "default_value": null,
        "options": [{"label":"A班","value":"A"}], // select/radio 必填
        "unit": "℃",                    // 可选单位(数字类)
        "min": null, "max": null,       // 数字范围
        "seq": 1                        // 显示顺序(升序)
      }, ...
    ]
    """
    __tablename__ = "form_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="模板名称")
    code = Column(String(64), unique=True, index=True, nullable=True, comment="模板编码（可选，便于跨环境迁移匹配）")
    category = Column(String(16), default="record", nullable=False, comment="record作业记录类 / guide通用表单类")
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True, comment="适用机台；NULL=通用模板，可用于任意机台")
    description = Column(String(500), nullable=True, comment="模板说明")
    field_schema = Column(JSON, default=list, nullable=False, comment="字段定义 JSON 数组")
    ref_stored_path = Column(String(512), nullable=True, comment="参考模板（空白PDF/Excel/图片）存储路径")
    ref_original_name = Column(String(255), nullable=True, comment="参考模板原始文件名")
    ref_file_size = Column(Integer, nullable=True, comment="参考模板字节")
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment")
    records = relationship("FormRecord", back_populates="template", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_form_tpl_cat_active", "category", "is_active"),
    )


class FormRecord(Base):
    """按模板填写生成的结构化表单记录。

    可与 ProcessDocument (category=record) 通过 process_documents.form_record_id 双向关联。
    文控扩展：状态流转 草稿 → 已提交 → 已审核/已作废
    - 已提交：提交人签 prepare
    - 已审核：审核人签 approve，记录锁定后禁止原地修改，只能走 Amendment
    """
    __tablename__ = "form_records"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("form_templates.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, comment="记录标题（默认为 模板名+批次+日期）")
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True)
    batch_no = Column(String(64), nullable=True, index=True, comment="批号(作业记录类)")
    shift = Column(String(16), nullable=True, comment="班次: A/B/C")
    production_date = Column(DateTime, nullable=True, comment="生产日期")
    status = Column(String(16), default="草稿", nullable=False, index=True, comment="草稿/已提交/已审核/已作废")
    remark = Column(String(500), nullable=True)
    filled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_at = Column(DateTime, nullable=True, comment="提交时间")
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="提交人（通常=filled_by）")
    audited = Column(Boolean, default=False, nullable=False, server_default=text("0"), index=True, comment="文控审核：审核后记录锁定")
    audited_at = Column(DateTime, nullable=True, comment="审核通过时间")
    audited_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    audit_signature = Column(String(128), nullable=True, comment="审核电子签名(SHA256 指纹)")
    audit_password_validated = Column(Boolean, default=False, nullable=False, server_default=text("0"), comment="审核时是否二次校验密码")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("FormTemplate", back_populates="records")
    values = relationship("FormRecordValue", back_populates="record", cascade="all, delete-orphan")
    process_documents = relationship("ProcessDocument", back_populates="form_record")
    amendments = relationship("FormRecordAmendment", back_populates="record", cascade="all, delete-orphan", order_by="FormRecordAmendment.amended_at.desc()")


class FormRecordValue(Base):
    """表单单字段填写值（JSON 存储，兼容文本/数字/布尔/数组）。"""
    __tablename__ = "form_record_values"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("form_records.id", ondelete="CASCADE"), nullable=False, index=True)
    field_key = Column(String(64), nullable=False, comment="对应模板 field_schema 中的 key")
    field_label_snapshot = Column(String(255), nullable=True, comment="快照字段标签(便于模板改动后回看)")
    field_value = Column(JSON, nullable=True, comment="填写值；任何 JSON 合法类型")

    record = relationship("FormRecord", back_populates="values")

    __table_args__ = (
        UniqueConstraint("record_id", "field_key", name="uq_form_record_values_record_field"),
    )


class FormRecordAmendment(Base):
    """已审核记录的附加修正（对应体系要求：记录修改需留痕+原因+签名）。

    不允许修改原有字段值，只能在此追加：改了哪个字段、原值、新值、原因、
    修改人签名（二次密码校验）、审核人是否批准过修正。
    """
    __tablename__ = "form_record_amendments"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("form_records.id", ondelete="CASCADE"), nullable=False, index=True)
    field_key = Column(String(64), nullable=False, comment="被修正字段 key；* 代表备注/附加说明级")
    field_label = Column(String(255), nullable=True)
    original_value = Column(JSON, nullable=True)
    corrected_value = Column(JSON, nullable=True)
    reason = Column(String(500), nullable=False, comment="修正原因：看错/写错/漏检/客户要求/设备重测…")

    amended_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amended_by_username = Column(String(64), nullable=False)
    amended_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    amendment_signature = Column(String(128), nullable=False, comment="修正人电子签名(含密码校验)")
    password_validated = Column(Boolean, default=False, nullable=False)

    approved = Column(Boolean, nullable=True, comment="审核人批准(可选)；NULL=待批")
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    record = relationship("FormRecord", back_populates="amendments")


# ============ 模块 M: P0 安全检查 ============

class SafetyInspection(Base):
    """P0 安全检查（安全装置/特种设备/环保/消防）。"""
    __tablename__ = "safety_inspections"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    check_type = Column(String(32), nullable=False, comment="检查类型: safety_device/特种设备/环保/消防")
    check_name = Column(String(255), nullable=False, comment="检查项目名称")
    check_standard = Column(Text, nullable=True, comment="检查标准/要求")
    frequency = Column(String(32), nullable=True, comment="频次: daily/weekly/monthly/quarterly/yearly")
    last_check_date = Column(DateTime, nullable=True)
    next_check_date = Column(DateTime, nullable=True, index=True)
    result = Column(String(16), default="pending", comment="pending/pass/fail/n_a")
    findings = Column(Text, nullable=True, comment="检查发现")
    corrective_action = Column(Text, nullable=True, comment="整改措施")
    checked_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    checked_by_name = Column(String(64), nullable=True)
    certificate_no = Column(String(128), nullable=True, comment="特种设备检验证书编号")
    certificate_expiry = Column(DateTime, nullable=True, comment="证书到期日")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    equipment = relationship("Equipment")


# ============ 模块 3: 设备生命周期 T0-T3 ============

class EquipmentLifecycle(Base):
    """设备生命周期阶段记录"""
    __tablename__ = "equipment_lifecycle"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    stage = Column(String(16), nullable=False, comment="阶段: T0选型/T1采购/T2安装调试/T3量产移交")
    stage_date = Column(DateTime, nullable=True, comment="阶段日期")
    title = Column(String(255), nullable=False, comment="阶段标题")
    description = Column(Text, nullable=True, comment="描述")
    # T0选型
    vendor_candidates = Column(Text, nullable=True, comment="候选供应商(JSON)")
    selected_vendor = Column(String(255), nullable=True, comment="选定供应商")
    ur_summary = Column(Text, nullable=True, comment="URS用户需求摘要")
    # T1采购
    po_no = Column(String(128), nullable=True, comment="采购订单号")
    po_amount = Column(Numeric(12, 2), nullable=True, comment="采购金额")
    delivery_date = Column(DateTime, nullable=True, comment="交货日期")
    # T2安装调试
    fat_date = Column(DateTime, nullable=True, comment="FAT出厂验收日期")
    fat_result = Column(String(16), nullable=True, comment="FAT结果: pass/fail/conditional")
    fat_notes = Column(Text, nullable=True, comment="FAT备注")
    sat_date = Column(DateTime, nullable=True, comment="SAT现场验收日期")
    sat_result = Column(String(16), nullable=True, comment="SAT结果")
    sat_notes = Column(Text, nullable=True, comment="SAT备注")
    commissioning_date = Column(DateTime, nullable=True, comment="安装调试日期")
    commissioning_notes = Column(Text, nullable=True, comment="调试记录")
    # T3量产移交
    handover_date = Column(DateTime, nullable=True, comment="量产移交日期")
    handover_to = Column(String(128), nullable=True, comment="移交给谁")
    acceptance_result = Column(String(16), nullable=True, comment="验收结果: pass/fail/conditional")
    acceptance_notes = Column(Text, nullable=True, comment="验收备注")
    # 附件
    attachment_path = Column(String(512), nullable=True, comment="附件路径(FAT报告/SAT报告等)")
    status = Column(String(16), default="in_progress", comment="in_progress/completed/aborted")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    equipment = relationship("Equipment")


# ============ 模块 4: 润滑管理 ============

class LubricationPoint(Base):
    """润滑点定义（五定卡）"""
    __tablename__ = "lubrication_points"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    point_name = Column(String(128), nullable=False, comment="润滑部位名称")
    point_code = Column(String(64), nullable=True, comment="润滑点编号")
    # 五定
    fixed_location = Column(String(255), nullable=True, comment="定点: 润滑位置描述")
    fixed_person_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="定人: 负责人")
    fixed_person_name = Column(String(64), nullable=True)
    fixed_frequency = Column(String(32), nullable=True, comment="定时: 频次 daily/weekly/monthly/quarterly")
    fixed_oil_type = Column(String(128), nullable=True, comment="定质: 润滑油/脂牌号")
    fixed_quantity = Column(String(64), nullable=True, comment="定量: 每次用量")
    # 计划
    next_lubrication_date = Column(DateTime, nullable=True, index=True, comment="下次润滑日期")
    enabled = Column(Boolean, default=True, nullable=False)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    equipment = relationship("Equipment")
    records = relationship("LubricationRecord", back_populates="point", cascade="all, delete-orphan")


class LubricationRecord(Base):
    """润滑执行记录"""
    __tablename__ = "lubrication_records"
    id = Column(Integer, primary_key=True, index=True)
    point_id = Column(Integer, ForeignKey("lubrication_points.id"), nullable=False, index=True)
    lubrication_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    oil_type_used = Column(String(128), nullable=True, comment="实际使用油/脂牌号")
    quantity_used = Column(String(64), nullable=True, comment="实际用量")
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    performed_by_name = Column(String(64), nullable=True)
    result = Column(String(16), default="done", comment="done/abnormal")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    point = relationship("LubricationPoint", back_populates="records")


# ============ 模块5: P6 故障知识库 ============

class KnowledgeEntry(Base):
    """故障知识库条目"""
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, comment="故障标题")
    symptom = Column(Text, nullable=True, comment="故障现象描述")
    fault_category = Column(String(64), nullable=True, comment="故障分类: mechanical/electrical/process/software/pneumatic/other")
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True, comment="关联设备(可空,表示通用)")
    equipment_model = Column(String(128), nullable=True, comment="设备型号(用于跨设备复用)")
    root_cause = Column(Text, nullable=True, comment="根因分析")
    solution = Column(Text, nullable=True, comment="处置措施")
    prevention = Column(Text, nullable=True, comment="预防措施")
    source_work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, comment="来源工单ID")
    source_d8_report_id = Column(Integer, ForeignKey("d8_reports.id"), nullable=True, comment="来源8D报告ID")
    tags = Column(String(512), nullable=True, comment="标签(逗号分隔)")
    views = Column(Integer, default=0, nullable=False, comment="浏览次数")
    recurrence_count = Column(Integer, default=0, nullable=False, comment="复发次数")
    status = Column(String(16), default="active", comment="active/archived")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_name = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    equipment = relationship("Equipment")


# ============ 审计日志 ============

class AuditLog(Base):
    """安全审计日志（登录/改密/用户管理等敏感操作）。"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(64), nullable=False, index=True, comment="LOGIN_OK/LOGIN_FAIL/LOGIN_LOCKED/LOGOUT/PASSWORD_CHANGED/PASSWORD_RESET/USER_CREATE/USER_UPDATE/USER_DELETE/USER_UNLOCK")
    actor = Column(String(64), nullable=True, index=True, comment="操作者用户名")
    target = Column(String(64), nullable=True, comment="被操作对象用户名")
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    detail = Column(String(500), nullable=True, comment="补充信息")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ============ 模块6: P7 设备成本 LCC ============

class EquipmentCost(Base):
    """设备成本记录"""
    __tablename__ = "equipment_costs"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    cost_type = Column(String(32), nullable=False, comment="成本类型: procurement/maintenance/spare_part/energy/depreciation/scrap")
    cost_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, comment="金额")
    description = Column(String(500), nullable=True, comment="费用说明")
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, comment="关联工单")
    spare_part_id = Column(Integer, ForeignKey("spare_parts.id"), nullable=True, comment="关联备件")
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    recorded_by_name = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    equipment = relationship("Equipment")
