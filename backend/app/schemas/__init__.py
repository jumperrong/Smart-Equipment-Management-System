from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.models import (
    UserRole, EquipmentStatus, WorkOrderType, WorkOrderStatus, FaultCategory,
    D8Status, SkillLevel, InventoryStatus, ApplicationType, ApplicationStatus,
    DictionaryCategory,
)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # 安全提示：true = 使用默认/弱密码或首次登录，要求跳修改密码
    must_change_password: bool = False
    # 账户是否临时锁定
    locked: bool = False
    lock_remaining_minutes: int = 0


class RefreshTokenIn(BaseModel):
    refresh_token: str


class LoginPayload(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class UserBase(BaseModel):
    username: str = Field(..., max_length=64)
    full_name: Optional[str] = Field(None, max_length=128)
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    must_change_password: bool = False


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)
    must_change_password: Optional[bool] = None
    locked_until: Optional[datetime] = None


class UserOut(UserBase):
    id: int
    must_change_password: bool = False
    locked_until: Optional[datetime] = None
    failed_login_count: int = 0
    last_password_changed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Equipment ----------

class EquipmentBase(BaseModel):
    name: str = Field(..., max_length=128)
    asset_no: Optional[str] = Field(None, max_length=64)
    factory: Optional[str] = Field(None, max_length=64)
    area: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    vendor: Optional[str] = Field(None, max_length=128)
    serial_no: Optional[str] = Field(None, max_length=128)
    install_date: Optional[datetime] = None
    theoretical_cycle: Optional[float] = Field(None, gt=0)
    spec: Optional[dict] = None
    description: Optional[str] = None
    is_active: bool = True


class EquipmentCreate(EquipmentBase):
    current_status: EquipmentStatus = EquipmentStatus.OFFLINE


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    asset_no: Optional[str] = None
    factory: Optional[str] = None
    area: Optional[str] = None
    model: Optional[str] = None
    vendor: Optional[str] = None
    serial_no: Optional[str] = None
    install_date: Optional[datetime] = None
    theoretical_cycle: Optional[float] = None
    spec: Optional[dict] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class EquipmentOut(EquipmentBase):
    id: int
    current_status: EquipmentStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Equipment Status Log ----------

class StatusLogBase(BaseModel):
    to_status: EquipmentStatus
    start_time: Optional[datetime] = None
    reason_code: Optional[str] = Field(None, max_length=64)
    reason_detail: Optional[str] = Field(None, max_length=255)
    remark: Optional[str] = Field(None, max_length=255)
    # 当切到 DOWN 时用于自动派发 REPAIR 工单
    urgency: Optional[str] = Field("NORMAL", max_length=16, description="紧急度 LOW/NORMAL/HIGH/CRITICAL")
    fault_phenomenon: Optional[str] = Field(None, max_length=500, description="故障现象(切DOWN时必填,自动创工单标题/描述)")


class StatusLogCreate(StatusLogBase):
    equipment_id: Optional[int] = None


class StatusLogClose(BaseModel):
    end_time: Optional[datetime] = None


class StatusLogOut(StatusLogBase):
    id: int
    equipment_id: int
    from_status: Optional[EquipmentStatus] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    operator_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 模块 A: 设备附件 ============

class AttachmentOut(BaseModel):
    id: int
    equipment_id: int
    filename: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentMeta(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None


# ============ 模块 D: 备件 ============

class SparePartBase(BaseModel):
    sku: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    spec: Optional[str] = None
    brand: Optional[str] = None
    unit: str = "个"
    safety_stock: int = 0
    current_stock: int = 0
    unit_price: float = 0
    location: Optional[str] = None
    remark: Optional[str] = None


class SparePartCreate(SparePartBase):
    pass


class SparePartUpdate(BaseModel):
    name: Optional[str] = None
    spec: Optional[str] = None
    brand: Optional[str] = None
    unit: Optional[str] = None
    safety_stock: Optional[int] = None
    unit_price: Optional[float] = None
    location: Optional[str] = None
    remark: Optional[str] = None


class SparePartOut(SparePartBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StockMovement(BaseModel):
    movement_type: str = Field(..., description="IN/OUT/ADJUST")
    qty: int = Field(..., gt=0)
    remark: Optional[str] = None


class MovementOut(BaseModel):
    id: int
    spare_part_id: int
    movement_type: str
    qty: int
    before_stock: Optional[int] = None
    after_stock: Optional[int] = None
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None
    operator_id: Optional[int] = None
    remark: Optional[str] = None
    created_at: datetime
    spare_part: Optional[SparePartOut] = None

    class Config:
        from_attributes = True


class SparePartStockSummary(BaseModel):
    """备件库存概览统计"""
    total_skus: int = 0                   # 总品种数
    total_qty: int = 0                    # 总库存数量
    total_value: float = 0.0              # 总库存金额（current_stock * unit_price）
    low_stock_count: int = 0              # 低于安全库存的 SKU 数
    out_of_stock_count: int = 0           # 断货的 SKU 数（current_stock == 0）


class EquipmentSparePartCreate(BaseModel):
    spare_part_id: int
    qty_per: int = 1
    remark: Optional[str] = None


class EquipmentSparePartOut(BaseModel):
    id: int
    equipment_id: int
    spare_part_id: int
    qty_per: int
    remark: Optional[str] = None
    spare_part: Optional[SparePartOut] = None

    class Config:
        from_attributes = True


# ============ 模块 B: 点检 ============

class InspectionItemBase(BaseModel):
    seq: int = 0
    name: str = Field(..., max_length=128)
    standard: Optional[str] = None
    required: bool = True


class InspectionItemCreate(InspectionItemBase):
    pass


class InspectionItemOut(InspectionItemBase):
    id: int
    template_id: int

    class Config:
        from_attributes = True


class InspectionTemplateBase(BaseModel):
    name: str = Field(..., max_length=128)
    equipment_id: Optional[int] = None
    frequency: str = "DAILY"
    description: Optional[str] = None
    is_active: bool = True


class InspectionTemplateCreate(InspectionTemplateBase):
    items: List[InspectionItemCreate] = Field(default_factory=list)


class InspectionTemplateUpdate(BaseModel):
    name: Optional[str] = None
    equipment_id: Optional[int] = None
    frequency: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    items: Optional[List[InspectionItemCreate]] = None


class InspectionTemplateOut(InspectionTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    items: List[InspectionItemOut] = []

    class Config:
        from_attributes = True


class InspectionResultIn(BaseModel):
    item_id: Optional[int] = None
    item_name: str
    result: str = Field(..., description="OK/NG/NA")
    value: Optional[str] = None
    remark: Optional[str] = None


class InspectionRecordCreate(BaseModel):
    template_id: int
    equipment_id: Optional[int] = None
    shift: Optional[str] = None
    inspect_time: Optional[datetime] = None
    remark: Optional[str] = None
    results: List[InspectionResultIn] = Field(default_factory=list)


class InspectionResultOut(InspectionResultIn):
    id: int
    record_id: int

    class Config:
        from_attributes = True


class InspectionRecordOut(BaseModel):
    id: int
    template_id: int
    equipment_id: Optional[int] = None
    shift: Optional[str] = None
    inspect_time: datetime
    inspector_id: Optional[int] = None
    overall_result: str
    remark: Optional[str] = None
    created_at: datetime
    results: List[InspectionResultOut] = []

    class Config:
        from_attributes = True


# ============ 模块 C: 工单 / 报修 / PM ============

class PMPlanBase(BaseModel):
    equipment_id: int
    name: str = Field(..., max_length=128)
    cycle_days: int = Field(..., gt=0)
    items: List[str] = Field(default_factory=list)
    next_due_date: Optional[datetime] = None
    planned_start_hour: int = Field(9, ge=0, le=23, description="计划开始时段(0-23点)")
    planned_duration_minutes: int = Field(120, gt=0, description="计划持续时长(分钟)")
    is_active: bool = True


class PMPlanCreate(PMPlanBase):
    pass


class PMPlanUpdate(BaseModel):
    equipment_id: Optional[int] = None
    name: Optional[str] = None
    cycle_days: Optional[int] = None
    items: Optional[List[str]] = None
    next_due_date: Optional[datetime] = None
    planned_start_hour: Optional[int] = Field(None, ge=0, le=23)
    planned_duration_minutes: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None


class PMPlanOut(PMPlanBase):
    id: int
    last_executed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RepairReportCreate(BaseModel):
    equipment_id: int
    phenomenon: str
    urgency: str = "NORMAL"


class RepairReportOut(BaseModel):
    id: int
    equipment_id: int
    reporter_id: Optional[int] = None
    phenomenon: str
    urgency: str
    reported_at: datetime
    work_order_id: Optional[int] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class FiveWhyIn(BaseModel):
    seq: int = Field(..., ge=1, le=5)
    question: str
    answer: Optional[str] = None


class FiveWhyOut(BaseModel):
    id: int
    work_order_id: int
    seq: int
    question: str
    answer: Optional[str] = None

    class Config:
        from_attributes = True


class SparePartUsageIn(BaseModel):
    spare_part_id: int
    qty: int = Field(..., gt=0)
    remark: Optional[str] = None


class SparePartUsageOut(BaseModel):
    id: int
    work_order_id: int
    spare_part_id: int
    qty: int
    movement_id: Optional[int] = None
    remark: Optional[str] = None
    spare_part: Optional[SparePartOut] = None

    class Config:
        from_attributes = True


class WorkOrderCreate(BaseModel):
    type: WorkOrderType
    equipment_id: int
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    urgency: str = "NORMAL"
    pm_plan_id: Optional[int] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    remark: Optional[str] = None


class WorkOrderUpdate(BaseModel):
    status: Optional[WorkOrderStatus] = None
    assignee_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    urgency: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    remark: Optional[str] = None


class FaultAnalysisIn(BaseModel):
    fault_category: Optional[FaultCategory] = None
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    prevention: Optional[str] = None
    five_whys: Optional[List[FiveWhyIn]] = None


class WorkOrderOut(BaseModel):
    id: int
    order_no: str
    type: WorkOrderType
    status: WorkOrderStatus
    equipment_id: int
    title: str
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    urgency: str = "NORMAL"
    pm_plan_id: Optional[int] = None
    status_log_id: Optional[int] = None
    fault_category: Optional[FaultCategory] = None
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    prevention: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # SLA 字段
    sla_response_minutes: Optional[int] = None
    sla_resolution_minutes: Optional[int] = None
    actual_response_minutes: Optional[int] = None
    actual_resolution_minutes: Optional[int] = None
    sla_breach: bool = False
    escalated: bool = False
    escalated_to_id: Optional[int] = None
    escalated_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    five_whys: List[FiveWhyOut] = []
    spare_usages: List[SparePartUsageOut] = []
    # 工单持续时长（计算字段，前端展示用）
    duration_text: Optional[str] = None
    duration_hours: Optional[float] = None

    class Config:
        from_attributes = True


# ============ 模块 E: 品管工具 (8D / FMEA) ============

class D8ReportBase(BaseModel):
    equipment_id: int
    work_order_id: Optional[int] = None
    title: str = Field(..., max_length=255)
    problem: Optional[str] = None
    d1_team: Optional[str] = None
    d2_problem_desc: Optional[str] = None
    d3_interim: Optional[str] = None
    d4_root_cause: Optional[str] = None
    d5_permanent: Optional[str] = None
    d6_implement: Optional[str] = None
    d7_prevent: Optional[str] = None
    d8_recognition: Optional[str] = None
    status: D8Status = D8Status.OPEN
    owner_id: Optional[int] = None


class D8ReportCreate(D8ReportBase):
    pass


class D8ReportUpdate(BaseModel):
    title: Optional[str] = None
    problem: Optional[str] = None
    d1_team: Optional[str] = None
    d2_problem_desc: Optional[str] = None
    d3_interim: Optional[str] = None
    d4_root_cause: Optional[str] = None
    d5_permanent: Optional[str] = None
    d6_implement: Optional[str] = None
    d7_prevent: Optional[str] = None
    d8_recognition: Optional[str] = None
    status: Optional[D8Status] = None
    owner_id: Optional[int] = None


class D8ReportOut(D8ReportBase):
    id: int
    report_no: str
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FMEAItemBase(BaseModel):
    seq: int = 0
    process_step: Optional[str] = None
    failure_mode: str = Field(..., max_length=255)
    failure_effect: Optional[str] = None
    cause: Optional[str] = None
    severity: int = Field(5, ge=1, le=10)
    occurrence: int = Field(5, ge=1, le=10)
    detection: int = Field(5, ge=1, le=10)
    recommended_action: Optional[str] = None
    action_owner_id: Optional[int] = None
    action_due_date: Optional[datetime] = None
    action_status: str = "OPEN"
    action_result: Optional[str] = None
    remark: Optional[str] = None


class FMEAItemCreate(FMEAItemBase):
    pass


class FMEAItemOut(FMEAItemBase):
    id: int
    fmea_id: int
    rpn: int

    class Config:
        from_attributes = True


class FMEABase(BaseModel):
    equipment_id: int
    name: str = Field(..., max_length=255)
    version: str = "1.0"
    is_active: bool = True


class FMEACreate(FMEABase):
    items: List[FMEAItemCreate] = Field(default_factory=list)


class FMEAUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    items: Optional[List[FMEAItemCreate]] = None


class FMEAOut(FMEABase):
    id: int
    created_at: datetime
    updated_at: datetime
    items: List[FMEAItemOut] = []

    class Config:
        from_attributes = True


# ============ 模块 F: 环境核查 ============

class EnvironmentLogBase(BaseModel):
    log_date: datetime
    factory: Optional[str] = None
    area: Optional[str] = None
    shift: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    cleanliness: Optional[str] = None
    particles: Optional[float] = None
    pressure: Optional[float] = None
    result: str = "OK"
    inspector_id: Optional[int] = None
    remark: Optional[str] = None


class EnvironmentLogCreate(EnvironmentLogBase):
    pass


class EnvironmentLogOut(EnvironmentLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 模块 G: 人员资质 / 培训 / 技能矩阵 ============

class QualificationBase(BaseModel):
    user_id: int
    equipment_id: Optional[int] = None
    skill_level: SkillLevel = SkillLevel.TRAINING
    certified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    certified_by: Optional[str] = None
    score: Optional[float] = None
    remark: Optional[str] = None
    is_active: bool = True


class QualificationCreate(QualificationBase):
    pass


class QualificationUpdate(BaseModel):
    skill_level: Optional[SkillLevel] = None
    certified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    certified_by: Optional[str] = None
    score: Optional[float] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class QualificationOut(QualificationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TrainingAttendeeBase(BaseModel):
    user_id: int
    attendance: str = "PRESENT"
    score: Optional[float] = None
    passed: bool = False
    remark: Optional[str] = None


class TrainingAttendeeCreate(TrainingAttendeeBase):
    pass


class TrainingAttendeeOut(TrainingAttendeeBase):
    id: int
    training_id: int

    class Config:
        from_attributes = True


class TrainingBase(BaseModel):
    name: str = Field(..., max_length=255)
    equipment_id: Optional[int] = None
    trainer_id: Optional[int] = None
    planned_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    content: Optional[str] = None
    status: str = "PLANNED"
    remark: Optional[str] = None


class TrainingCreate(TrainingBase):
    attendees: List[TrainingAttendeeCreate] = Field(default_factory=list)


class TrainingOut(TrainingBase):
    id: int
    created_at: datetime
    attendees: List[TrainingAttendeeOut] = []

    class Config:
        from_attributes = True


# ============ 模块 H: 资产盘点 / 调拨报废 ============

class AssetInventoryLineBase(BaseModel):
    equipment_id: int
    system_status: Optional[str] = None
    actual_found: bool = False
    location_match: bool = False
    result: str = "PENDING"
    checked_by: Optional[int] = None
    checked_at: Optional[datetime] = None
    remark: Optional[str] = None


class AssetInventoryLineUpdate(BaseModel):
    actual_found: Optional[bool] = None
    location_match: Optional[bool] = None
    result: Optional[str] = None
    remark: Optional[str] = None


class AssetInventoryLineOut(AssetInventoryLineBase):
    id: int
    inventory_id: int

    class Config:
        from_attributes = True


class AssetInventoryBase(BaseModel):
    name: str = Field(..., max_length=255)
    plan_date: Optional[datetime] = None
    status: InventoryStatus = InventoryStatus.PLANNED
    remark: Optional[str] = None


class AssetInventoryCreate(AssetInventoryBase):
    equipment_ids: List[int] = Field(default_factory=list, description="一次性纳入盘点的设备")


class AssetInventoryOut(AssetInventoryBase):
    id: int
    inventory_no: str
    created_by: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    lines: List[AssetInventoryLineOut] = []

    class Config:
        from_attributes = True


class AssetApplicationBase(BaseModel):
    type: ApplicationType
    equipment_id: int
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    reason: Optional[str] = None
    remark: Optional[str] = None


class AssetApplicationCreate(AssetApplicationBase):
    pass


class AssetApplicationOut(AssetApplicationBase):
    id: int
    application_no: str
    status: ApplicationStatus
    applicant_id: Optional[int] = None
    approver_id: Optional[int] = None
    applied_at: datetime
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssetApplicationApprove(BaseModel):
    decision: str = Field(..., description="APPROVED/REJECTED")
    remark: Optional[str] = None


# ============ 模块 I: 产品 / 生产记录 ============

class ProductBase(BaseModel):
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    spec: Optional[str] = None
    unit: str = "片"
    target_cycle: Optional[float] = Field(None, gt=0)
    remark: Optional[str] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    target_cycle: Optional[float] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductionRecordBase(BaseModel):
    equipment_id: int
    product_id: Optional[int] = None
    batch_no: Optional[str] = None
    plan_qty: int = 0
    input_qty: int = 0
    good_qty: int = 0
    defect_qty: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    ideal_cycle: Optional[float] = None
    operator_id: Optional[int] = None
    remark: Optional[str] = None


class ProductionRecordCreate(ProductionRecordBase):
    pass


class ProductionRecordUpdate(BaseModel):
    product_id: Optional[int] = None
    batch_no: Optional[str] = None
    plan_qty: Optional[int] = None
    input_qty: Optional[int] = None
    good_qty: Optional[int] = None
    defect_qty: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    ideal_cycle: Optional[float] = None
    operator_id: Optional[int] = None
    remark: Optional[str] = None


class ProductionRecordOut(ProductionRecordBase):
    id: int
    record_no: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ 看板聚合响应 ============

class DashboardEquipmentItem(BaseModel):
    id: int
    name: str
    asset_no: Optional[str] = None
    factory: Optional[str] = None
    area: Optional[str] = None
    current_status: EquipmentStatus
    status_start_time: datetime
    status_duration_minutes: float
    # 最近一次状态变更信息
    last_from_status: Optional[EquipmentStatus] = None
    last_to_status: Optional[EquipmentStatus] = None
    last_reason_code: Optional[str] = None
    last_reason_detail: Optional[str] = None
    last_operator_name: Optional[str] = None
    last_change_time: Optional[datetime] = None
    updated_at: datetime
    open_work_orders: int = 0
    last_work_order_no: Optional[str] = None
    last_production_no: Optional[str] = None
    last_product_name: Optional[str] = None
    last_good_qty: Optional[int] = None


class DashboardStatusLogItem(BaseModel):
    id: int
    equipment_id: int
    equipment_name: Optional[str] = None
    equipment_factory: Optional[str] = None
    equipment_area: Optional[str] = None
    from_status: Optional[EquipmentStatus] = None
    to_status: EquipmentStatus
    reason_code: Optional[str] = None
    start_time: datetime
    duration_minutes: Optional[float] = None


class DashboardWorkOrderItem(BaseModel):
    id: int
    order_no: str
    type: WorkOrderType
    status: WorkOrderStatus
    equipment_id: int
    equipment_name: Optional[str] = None
    title: str
    created_at: datetime


class DashboardProductionItem(BaseModel):
    id: int
    record_no: str
    equipment_id: int
    equipment_name: Optional[str] = None
    product_name: Optional[str] = None
    batch_no: Optional[str] = None
    good_qty: int = 0
    defect_qty: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class DashboardSummary(BaseModel):
    total: int = 0
    running: int = 0
    down: int = 0
    idle: int = 0
    pm: int = 0
    pm_overtime: int = 0  # PM 进行中且已超时的设备数
    engineering: int = 0
    offline: int = 0
    open_work_orders: int = 0
    today_production: int = 0
    today_good: int = 0
    today_defect: int = 0
    oee: float = 0.0


class DashboardOut(BaseModel):
    summary: DashboardSummary
    status_counts: dict
    equipments: List[DashboardEquipmentItem]
    recent_status_logs: List[DashboardStatusLogItem]
    recent_work_orders: List[DashboardWorkOrderItem]
    recent_production: List[DashboardProductionItem]


# ============ 模块 J: 系统字典/配置 ============

class DictionaryItemBase(BaseModel):
    category: DictionaryCategory
    code: str = Field(..., max_length=64)
    label: str = Field(..., max_length=128)
    value: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    remark: Optional[str] = None


class DictionaryItemCreate(DictionaryItemBase):
    pass


class DictionaryItemUpdate(BaseModel):
    label: Optional[str] = None
    value: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = None


class DictionaryItemOut(DictionaryItemBase):
    id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ 模块 K: 工艺文件 ============

class ProcessDocumentOut(BaseModel):
    id: int
    equipment_id: int
    category: Optional[str] = None
    doc_no: Optional[str] = None
    doc_class: Optional[str] = None
    doc_name: str
    doc_type: Optional[str] = None
    version: Optional[str] = None
    version_seq: Optional[int] = None
    group_id: Optional[str] = None
    is_latest: Optional[bool] = None
    status: str
    effective_date: Optional[datetime] = None
    review_cycle_month: Optional[int] = None
    next_review_date: Optional[datetime] = None
    batch_no: Optional[str] = None
    shift: Optional[str] = None
    production_date: Optional[datetime] = None
    stored_path: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[int] = None
    form_record_id: Optional[int] = None
    # 外来文件字段（doc_class=EXTERN 时使用）
    source_type: Optional[str] = None
    source_ref_no: Optional[str] = None
    received_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProcessDocumentUpdate(BaseModel):
    """仅允许修改元数据；状态、版本、文件通过专用 API 变更。"""
    doc_no: Optional[str] = None
    doc_class: Optional[str] = None
    doc_name: Optional[str] = None
    doc_type: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[datetime] = None
    description: Optional[str] = None
    batch_no: Optional[str] = None
    shift: Optional[str] = None
    production_date: Optional[datetime] = None
    review_cycle_month: Optional[int] = None
    # 外来文件字段
    source_type: Optional[str] = None
    source_ref_no: Optional[str] = None
    received_date: Optional[datetime] = None


class ProcessDocumentStatusTransition(BaseModel):
    """状态流转请求体。

    合法流转：
    - 草稿 → 审核中 / 生效 / 作废
    - 审核中 → 生效 / 作废 / 草稿（驳回退回）
    - 生效 → 作废
    其余流转(如生效→草稿、作废→任意)均非法。
    """
    status: str  # 目标状态：审核中 / 生效 / 作废 / 草稿
    effective_date: Optional[datetime] = None
    remark: Optional[str] = None


# ============ 模块 K2: 文档编号规则 ============

class DocNoRuleOut(BaseModel):
    id: int
    doc_class: str
    prefix: str
    use_equipment_code: bool
    use_year: bool
    use_month: bool
    seq_width: int
    next_seq: int
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocNoRuleCreate(BaseModel):
    doc_class: str = Field(..., max_length=16, description="文控分类: SOP/SIP/SPEC/FORM/RECORD/EXTERN")
    prefix: str = Field(..., max_length=16)
    use_equipment_code: bool = False
    use_year: bool = True
    use_month: bool = False
    seq_width: int = Field(3, ge=1, le=8)
    is_active: bool = True
    description: Optional[str] = None


class DocNoRuleUpdate(BaseModel):
    prefix: Optional[str] = None
    use_equipment_code: Optional[bool] = None
    use_year: Optional[bool] = None
    use_month: Optional[bool] = None
    seq_width: Optional[int] = Field(None, ge=1, le=8)
    next_seq: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    description: Optional[str] = None


class DocNoGenerateRequest(BaseModel):
    """根据编号规则生成文档编号。"""
    doc_class: str = Field(..., description="文控分类")
    equipment_id: Optional[int] = Field(None, description="机台ID（规则含机台码时使用）")


class DocNoGenerateResponse(BaseModel):
    doc_no: str
    rule_id: int
    seq: int


# ============ 模块 K3/K4/K5: 审批链 / 修订记录 / 分发 ============

# -------- 审批 --------
class ApprovalSignRequest(BaseModel):
    """签署时的 payload（编制/审核/批准/作废 通用）。

    需二次校验密码保证电子签名合规。
    """
    process_document_id: int
    stage: str = Field(..., description="prepare/review/approve/reject_prepare/reject_review/reject_approve")
    password: str = Field(..., max_length=128, description="签署人当前登录密码")
    comment: Optional[str] = Field(None, max_length=500, description="签署意见；驳回时必填原因")


class DocumentApprovalOut(BaseModel):
    id: int
    process_document_id: int
    stage: str
    stage_order: int
    result: str
    comment: Optional[str] = None
    signer_id: int
    signer_username: str
    signer_display_name: Optional[str] = None
    signer_role: Optional[str] = None
    signed_at: datetime
    password_validated: bool
    # 签名指纹只显示前缀（不可泄露全部）
    signature_tail: Optional[str] = None

    class Config:
        from_attributes = True


# -------- 修订 --------
class ChangeDetailItem(BaseModel):
    seq: int = Field(1, ge=1)
    change_type: str = Field("M", description="A=新增 M=修改 D=删除")
    page: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    impact: Optional[str] = None


class DocumentChangeLogCreate(BaseModel):
    process_document_id: int
    change_reason: str = Field(..., description="NEW/REV_VOID/REV_SPEC/REV_STEP/ENG_CHG/QC_NC/CUSTOMER")
    change_summary: str = Field(..., min_length=1, max_length=500)
    detail_items: List[ChangeDetailItem] = Field(default_factory=list)


class DocumentChangeLogOut(BaseModel):
    id: int
    process_document_id: int
    change_reason: str
    change_summary: str
    detail_items_json: Optional[List[ChangeDetailItem]] = None
    detail_items: Optional[List[ChangeDetailItem]] = None
    version: Optional[str] = None
    changed_by_id: Optional[int] = None
    changed_by_username: Optional[str] = None
    changed_at: Optional[datetime] = None
    created_by_id: int
    created_by_username: str
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def _backward_compat(self):
        if self.detail_items is None and self.detail_items_json is not None:
            self.detail_items = self.detail_items_json
        if self.changed_at is None:
            self.changed_at = self.created_at
        if self.changed_by_id is None:
            self.changed_by_id = self.created_by_id
        if self.changed_by_username is None:
            self.changed_by_username = self.created_by_username
        return self


# -------- 分发 --------
class DocumentDistributionCreate(BaseModel):
    process_document_id: int
    recipient_type: str = Field("USER", description="USER/ROLE/DEPARTMENT")
    recipient_ref: str = Field(..., max_length=64)
    hold_copies: int = Field(1, ge=1)
    medium: str = Field("E", description="E=电子 P=纸质")


class DocumentDistributionReturn(BaseModel):
    ids: List[int]
    return_note: Optional[str] = None


class DocumentDistributionOut(BaseModel):
    id: int
    process_document_id: int
    recipient_type: str
    recipient_ref: str
    recipient_name: Optional[str] = None
    hold_copies: int
    medium: str
    issued_at: datetime
    issued_by_id: Optional[int] = None
    distributed_by_username: Optional[str] = None
    returned: bool
    returned_at: Optional[datetime] = None
    return_note: Optional[str] = None
    status: Optional[str] = None
    distributed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def _derive_fields(self):
        if self.distributed_at is None:
            self.distributed_at = self.issued_at
        if self.status is None:
            if self.returned:
                self.status = "RETURNED"
            else:
                self.status = "DISTRIBUTED"
        return self


# ============ 模块 L: 表单模板与结构化表单记录 ============

class FormTemplateFieldDef(BaseModel):
    """单个字段定义（模板 field_schema 数组元素）。"""
    key: str = Field(..., max_length=64, description="字段唯一key,英文小写+下划线")
    type: str = Field(..., description="text / textarea / number / select / radio / date / datetime / time / boolean")
    label: str = Field(..., max_length=255, description="显示名")
    required: bool = False
    placeholder: Optional[str] = Field(None, max_length=255)
    default_value: Optional[object] = None
    options: Optional[List[dict]] = Field(None, description="select/radio 的选项 [{label, value}]")
    unit: Optional[str] = Field(None, max_length=16, description="单位如 ℃/g/min")
    min: Optional[float] = None
    max: Optional[float] = None
    seq: int = Field(0, ge=0, description="显示顺序(升序)")


class FormTemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    code: Optional[str] = Field(None, max_length=64)
    category: str = "record"
    equipment_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    field_schema: List[FormTemplateFieldDef] = Field(default_factory=list)
    is_active: bool = True


class FormTemplateCreate(FormTemplateBase):
    pass


class FormTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    code: Optional[str] = Field(None, max_length=64)
    category: Optional[str] = None
    equipment_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    field_schema: Optional[List[FormTemplateFieldDef]] = None
    is_active: Optional[bool] = None


class FormTemplateOut(FormTemplateBase):
    id: int
    ref_original_name: Optional[str] = None
    ref_file_size: Optional[int] = None
    has_ref_file: bool = False
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FormRecordKeyValue(BaseModel):
    """单字段填写值"""
    field_key: str = Field(..., max_length=64)
    field_value: Optional[object] = None


class FormRecordBase(BaseModel):
    template_id: int
    title: Optional[str] = Field(None, max_length=255, description="留空则自动生成: 模板名 + 批次/日期")
    equipment_id: Optional[int] = None
    batch_no: Optional[str] = Field(None, max_length=64)
    shift: Optional[str] = Field(None, max_length=16)
    production_date: Optional[datetime] = None
    remark: Optional[str] = Field(None, max_length=500)


class FormRecordCreate(FormRecordBase):
    """创建表单记录：可选 initial_values（未填则生成空值）。"""
    values: List[FormRecordKeyValue] = Field(default_factory=list)
    auto_submit: bool = Field(False, description="true = 直接变为已提交状态；否则=草稿")
    link_process_doc: bool = Field(True, description="true = 同步创建一条 process_documents (category=record) 关联条目,列表中可直接看到")


class FormRecordUpdate(BaseModel):
    """更新表单记录：元信息 + values 增量覆盖。"""
    title: Optional[str] = Field(None, max_length=255)
    equipment_id: Optional[int] = None
    batch_no: Optional[str] = Field(None, max_length=64)
    shift: Optional[str] = Field(None, max_length=16)
    production_date: Optional[datetime] = None
    remark: Optional[str] = Field(None, max_length=500)
    values: Optional[List[FormRecordKeyValue]] = None


class FormRecordOut(FormRecordBase):
    id: int
    status: str
    filled_by: Optional[int] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[int] = None
    audited: bool = False
    audited_at: Optional[datetime] = None
    audited_by: Optional[int] = None
    audit_password_validated: bool = False
    values: List[FormRecordKeyValue] = Field(default_factory=list)
    # 展示辅助：模板信息快照
    template_name: Optional[str] = None
    template_category: Optional[str] = None
    equipment_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 表单审核签名（二次密码校验）
class FormRecordAuditRequest(BaseModel):
    record_id: int
    password: str = Field(..., max_length=128, description="审核人登录密码（二次校验）")
    comment: Optional[str] = Field(None, max_length=500)
    reject: bool = Field(False, description="True=驳回（状态回已提交）")


# 已审核记录附加修正
class FormRecordAmendmentCreate(BaseModel):
    record_id: int
    field_key: str = Field(..., max_length=64)
    field_label: Optional[str] = Field(None, max_length=255)
    original_value: Optional[object] = None
    corrected_value: Optional[object] = None
    reason: str = Field(..., min_length=1, max_length=500)
    password: str = Field(..., max_length=128, description="修正人登录密码（二次校验）")


class FormRecordAmendmentOut(BaseModel):
    id: int
    record_id: int
    field_key: str
    field_label: Optional[str] = None
    original_value: Optional[object] = None
    corrected_value: Optional[object] = None
    reason: str
    amended_by_id: int
    amended_by_username: str
    amended_at: datetime
    password_validated: bool
    approved: Optional[bool] = None
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def _derive_status(self):
        if self.status is None:
            if self.approved is None:
                self.status = "PENDING"
            elif self.approved:
                self.status = "APPROVED"
            else:
                self.status = "REJECTED"
        return self


# ============ 模块 M: P0 安全检查 ============

class SafetyInspectionBase(BaseModel):
    equipment_id: int
    check_type: str = Field(..., max_length=32, description="检查类型: safety_device/特种设备/环保/消防")
    check_name: str = Field(..., max_length=255)
    check_standard: Optional[str] = None
    frequency: Optional[str] = Field(None, description="daily/weekly/monthly/quarterly/yearly")
    last_check_date: Optional[datetime] = None
    next_check_date: Optional[datetime] = None
    result: str = "pending"
    findings: Optional[str] = None
    corrective_action: Optional[str] = None
    checked_by_id: Optional[int] = None
    checked_by_name: Optional[str] = None
    certificate_no: Optional[str] = None
    certificate_expiry: Optional[datetime] = None


class SafetyInspectionCreate(SafetyInspectionBase):
    pass


class SafetyInspectionUpdate(BaseModel):
    equipment_id: Optional[int] = None
    check_type: Optional[str] = None
    check_name: Optional[str] = None
    check_standard: Optional[str] = None
    frequency: Optional[str] = None
    last_check_date: Optional[datetime] = None
    next_check_date: Optional[datetime] = None
    result: Optional[str] = None
    findings: Optional[str] = None
    corrective_action: Optional[str] = None
    checked_by_id: Optional[int] = None
    checked_by_name: Optional[str] = None
    certificate_no: Optional[str] = None
    certificate_expiry: Optional[datetime] = None


class SafetyInspectionOut(SafetyInspectionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SafetyInspectionCheckIn(BaseModel):
    """执行检查的请求体。"""
    result: str = Field(..., description="pending/pass/fail/n_a")
    findings: Optional[str] = None
    corrective_action: Optional[str] = None


# ============ 模块 N: P1 工单 SLA ============

class SLASetRequest(BaseModel):
    """设置 SLA 目标。"""
    sla_response_minutes: Optional[int] = Field(None, ge=0, description="SLA目标响应时长(分钟)")
    sla_resolution_minutes: Optional[int] = Field(None, ge=0, description="SLA目标解决时长(分钟)")


class SLAEscalateRequest(BaseModel):
    """升级工单请求体。"""
    escalated_to_id: int = Field(..., description="升级到的目标用户ID")
    reassign: bool = Field(True, description="是否同时把工单指派给该上级")


class SLAStatsOut(BaseModel):
    """SLA 达成率统计响应。"""
    total: int = 0
    breached: int = 0
    achieved: int = 0
    achieve_rate: float = 0.0
    avg_response_minutes: float = 0.0
    avg_resolution_minutes: float = 0.0


# ============ 模块5: P6 故障知识库 ============

class KnowledgeEntryBase(BaseModel):
    title: str = Field(..., max_length=255)
    symptom: Optional[str] = None
    fault_category: Optional[str] = Field(None, max_length=64)
    equipment_id: Optional[int] = None
    equipment_model: Optional[str] = Field(None, max_length=128)
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    prevention: Optional[str] = None
    source_work_order_id: Optional[int] = None
    tags: Optional[str] = Field(None, max_length=512)
    status: str = "active"


class KnowledgeEntryCreate(KnowledgeEntryBase):
    pass


class KnowledgeEntryUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    symptom: Optional[str] = None
    fault_category: Optional[str] = Field(None, max_length=64)
    equipment_id: Optional[int] = None
    equipment_model: Optional[str] = Field(None, max_length=128)
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    prevention: Optional[str] = None
    tags: Optional[str] = Field(None, max_length=512)
    status: Optional[str] = None


class KnowledgeEntryOut(KnowledgeEntryBase):
    id: int
    views: int = 0
    recurrence_count: int = 0
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 从工单归档为知识条目
class KnowledgeFromWorkOrder(BaseModel):
    """从工单归档为知识库条目(可选覆盖字段)。"""
    title: Optional[str] = Field(None, max_length=255, description="留空则用工单标题")
    tags: Optional[str] = Field(None, max_length=512)
    equipment_model: Optional[str] = Field(None, max_length=128)
    fault_category: Optional[str] = Field(None, max_length=64)


# ============ 模块6: P7 设备成本 LCC ============

class EquipmentCostBase(BaseModel):
    equipment_id: int
    cost_type: str = Field(..., max_length=32)
    cost_date: Optional[datetime] = None
    amount: Decimal = Field(..., description="金额")
    description: Optional[str] = Field(None, max_length=500)
    work_order_id: Optional[int] = None
    spare_part_id: Optional[int] = None


class EquipmentCostCreate(EquipmentCostBase):
    pass


class EquipmentCostUpdate(BaseModel):
    cost_type: Optional[str] = Field(None, max_length=32)
    cost_date: Optional[datetime] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = Field(None, max_length=500)
    work_order_id: Optional[int] = None
    spare_part_id: Optional[int] = None


class EquipmentCostOut(EquipmentCostBase):
    id: int
    recorded_by_id: Optional[int] = None
    recorded_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 模块 3: 设备生命周期 T0-T3 ============

class EquipmentLifecycleBase(BaseModel):
    equipment_id: int
    stage: str = Field(..., max_length=16, description="阶段: T0选型/T1采购/T2安装调试/T3量产移交")
    stage_date: Optional[datetime] = None
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    # T0选型
    vendor_candidates: Optional[str] = None
    selected_vendor: Optional[str] = Field(None, max_length=255)
    ur_summary: Optional[str] = None
    # T1采购
    po_no: Optional[str] = Field(None, max_length=128)
    po_amount: Optional[Decimal] = None
    delivery_date: Optional[datetime] = None
    # T2安装调试
    fat_date: Optional[datetime] = None
    fat_result: Optional[str] = Field(None, max_length=16)
    fat_notes: Optional[str] = None
    sat_date: Optional[datetime] = None
    sat_result: Optional[str] = Field(None, max_length=16)
    sat_notes: Optional[str] = None
    commissioning_date: Optional[datetime] = None
    commissioning_notes: Optional[str] = None
    # T3量产移交
    handover_date: Optional[datetime] = None
    handover_to: Optional[str] = Field(None, max_length=128)
    acceptance_result: Optional[str] = Field(None, max_length=16)
    acceptance_notes: Optional[str] = None
    # 附件
    attachment_path: Optional[str] = Field(None, max_length=512)
    status: str = "in_progress"


class EquipmentLifecycleCreate(EquipmentLifecycleBase):
    pass


class EquipmentLifecycleUpdate(BaseModel):
    stage: Optional[str] = Field(None, max_length=16)
    stage_date: Optional[datetime] = None
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    vendor_candidates: Optional[str] = None
    selected_vendor: Optional[str] = None
    ur_summary: Optional[str] = None
    po_no: Optional[str] = None
    po_amount: Optional[Decimal] = None
    delivery_date: Optional[datetime] = None
    fat_date: Optional[datetime] = None
    fat_result: Optional[str] = None
    fat_notes: Optional[str] = None
    sat_date: Optional[datetime] = None
    sat_result: Optional[str] = None
    sat_notes: Optional[str] = None
    commissioning_date: Optional[datetime] = None
    commissioning_notes: Optional[str] = None
    handover_date: Optional[datetime] = None
    handover_to: Optional[str] = None
    acceptance_result: Optional[str] = None
    acceptance_notes: Optional[str] = None
    attachment_path: Optional[str] = None
    status: Optional[str] = None


class EquipmentLifecycleOut(EquipmentLifecycleBase):
    id: int
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ 模块 4: 润滑管理 ============

class LubricationPointBase(BaseModel):
    equipment_id: int
    point_name: str = Field(..., max_length=128)
    point_code: Optional[str] = Field(None, max_length=64)
    # 五定
    fixed_location: Optional[str] = Field(None, max_length=255)
    fixed_person_id: Optional[int] = None
    fixed_person_name: Optional[str] = Field(None, max_length=64)
    fixed_frequency: Optional[str] = Field(None, max_length=32)
    fixed_oil_type: Optional[str] = Field(None, max_length=128)
    fixed_quantity: Optional[str] = Field(None, max_length=64)
    # 计划
    next_lubrication_date: Optional[datetime] = None
    enabled: bool = True
    remark: Optional[str] = None


class LubricationPointCreate(LubricationPointBase):
    pass


class LubricationPointUpdate(BaseModel):
    point_name: Optional[str] = Field(None, max_length=128)
    point_code: Optional[str] = Field(None, max_length=64)
    fixed_location: Optional[str] = None
    fixed_person_id: Optional[int] = None
    fixed_person_name: Optional[str] = None
    fixed_frequency: Optional[str] = None
    fixed_oil_type: Optional[str] = None
    fixed_quantity: Optional[str] = None
    next_lubrication_date: Optional[datetime] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None


class LubricationPointOut(LubricationPointBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LubricationRecordBase(BaseModel):
    point_id: int
    lubrication_date: Optional[datetime] = None
    oil_type_used: Optional[str] = Field(None, max_length=128)
    quantity_used: Optional[str] = Field(None, max_length=64)
    performed_by_id: Optional[int] = None
    performed_by_name: Optional[str] = Field(None, max_length=64)
    result: str = "done"
    notes: Optional[str] = None


class LubricationRecordCreate(LubricationRecordBase):
    pass


class LubricationRecordOut(LubricationRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

