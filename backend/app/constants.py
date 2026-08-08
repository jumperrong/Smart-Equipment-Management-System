"""权限功能键清单与默认角色矩阵。

设计：
- 每个权限点由 (feature_key, label, group) 描述
- DEFAULT_ROLE_MATRIX 给出每个角色在没被管理员调整前的默认放行情况
- 启动时由 permission_service.seed_default_permissions 把缺失的 (role, feature_key) 补齐到 DB
- 之后管理员在界面调整 = 直接改 DB 记录
- require_permission(feature_key) 在运行时查 DB，无记录则回退到 DEFAULT_ROLE_MATRIX

新增功能时只需在 FEATURES 里追加一项，重启后会自动补齐各角色默认值。
"""
from app.models import UserRole


# (feature_key, label, group, default_allowed_roles)
# default_allowed_roles 用角色字符串列表表示，与 UserRole.value 对齐
_FEATURES_DEF = [
    # 认证与用户
    ("auth.user_manage",        "用户管理（增删改）",        "认证与用户",   ["admin"]),
    ("auth.reset_password",     "重置他人密码",              "认证与用户",   ["admin"]),

    # 设备
    ("equipment.write",         "设备编辑/新增",             "设备",         ["admin", "engineer"]),
    ("equipment.delete",         "设备删除",                  "设备",         ["admin"]),
    ("equipment.change_status", "设备状态变更/关闭",         "设备",         ["admin", "engineer", "operator"]),
    ("attachment.manage",       "设备附件上传/删除",          "设备",         ["admin", "engineer"]),

    # 备件
    ("spare_part.write",        "备件编辑/新增",              "备件",         ["admin", "engineer"]),
    ("spare_part.delete",       "备件删除",                   "备件",         ["admin"]),
    ("spare_part.movement",     "备件出入库",                 "备件",         ["admin", "engineer", "operator"]),
    ("spare_part.equipment_bind", "备件-设备绑定",            "备件",         ["admin", "engineer"]),

    # 点检
    ("inspection.template_write",  "点检模板编辑",            "点检",         ["admin", "engineer"]),
    ("inspection.template_delete", "点检模板删除",            "点检",         ["admin"]),
    ("inspection.record_create",   "点检记录提交",           "点检",         ["admin", "engineer", "operator"]),

    # 工单 / PM / 报修
    ("work_order.write",          "工单编辑/新建",            "工单/PM/报修", ["admin", "engineer"]),
    ("work_order.fault_analysis", "工单故障分析(5Why)",       "工单/PM/报修", ["admin", "engineer"]),
    ("work_order.spare_usage",    "工单备件领用",            "工单/PM/报修", ["admin", "engineer"]),
    ("pm_plan.write",             "PM计划编辑",               "工单/PM/报修", ["admin", "engineer"]),
    ("pm_plan.delete",            "PM计划删除",               "工单/PM/报修", ["admin"]),
    ("pm_plan.generate_due",      "生成到期PM工单",           "工单/PM/报修", ["admin", "engineer"]),
    ("repair_report.create",      "故障报修",                 "工单/PM/报修", ["admin", "engineer", "operator"]),
    ("repair_report.convert",     "报修转工单",               "工单/PM/报修", ["admin", "engineer"]),

    # 品管
    ("quality.d8_write",    "8D报告编辑",   "品管", ["admin", "engineer"]),
    ("quality.d8_delete",   "8D报告删除",   "品管", ["admin"]),
    ("quality.fmea_write",  "FMEA编辑",     "品管", ["admin", "engineer"]),
    ("quality.fmea_delete", "FMEA删除",     "品管", ["admin"]),

    # 环境
    ("environment.write",  "环境记录编辑", "环境", ["admin", "engineer", "operator"]),
    ("environment.delete", "环境记录删除", "环境", ["admin", "engineer"]),

    # 人员
    ("personnel.qualification_write",   "资质编辑",   "人员", ["admin", "engineer"]),
    ("personnel.qualification_delete",  "资质删除",   "人员", ["admin"]),
    ("personnel.training_write",        "培训编辑",   "人员", ["admin", "engineer"]),
    ("personnel.training_delete",       "培训删除",   "人员", ["admin"]),

    # 资产
    ("asset.inventory_write",        "盘点编辑",       "资产", ["admin", "engineer"]),
    ("asset.inventory_delete",       "盘点删除",       "资产", ["admin"]),
    ("asset.inventory_line_update",  "盘点明细更新",   "资产", ["admin", "engineer", "operator"]),
    ("asset.application_create",     "资产申请",       "资产", ["admin", "engineer"]),
    ("asset.application_approve",    "资产审批",       "资产", ["admin"]),
    ("asset.application_complete",   "资产处置完成",   "资产", ["admin", "engineer"]),

    # 生产
    ("production.product_write",   "产品编辑",       "生产", ["admin", "engineer"]),
    ("production.product_delete",   "产品删除",       "生产", ["admin"]),
    ("production.record_create",    "生产记录提交",   "生产", ["admin", "engineer", "operator"]),
    ("production.record_update",    "生产记录编辑",   "生产", ["admin", "engineer"]),
    ("production.record_delete",    "生产记录删除",   "生产", ["admin"]),

    # 系统
    ("dictionary.manage",          "字典管理",       "系统", ["admin"]),
    ("system.permission_manage",   "权限配置",       "系统", ["admin"]),
    ("system.settings_manage",     "系统设置(环境变量)", "系统", ["admin"]),
    ("system.ip_whitelist_manage",  "IP 白名单管理",  "系统", ["admin"]),
    ("system.restart_server",      "重启服务",       "系统", ["admin"]),
    ("system.backup_manage",       "系统备份/恢复",  "系统", ["admin"]),

    # 工艺文件
    ("process_doc.write",          "工艺文件上传/编辑", "工艺文件", ["admin", "process_engineer"]),
    ("process_doc.delete",         "工艺文件删除",      "工艺文件", ["admin"]),

    # 表单模板与结构化记录
    ("form_template.manage",       "表单模板管理(新增/编辑/删除/停用)", "表单与记录", ["admin", "process_engineer"]),
    ("form_record.fill",           "结构化表单记录填写与提交",            "表单与记录", ["admin", "engineer", "process_engineer", "operator"]),
    ("form_record.delete",         "结构化表单记录删除",                  "表单与记录", ["admin"]),
]


class FeatureDef:
    __slots__ = ("key", "label", "group", "default_roles")

    def __init__(self, key, label, group, default_roles):
        self.key = key
        self.label = label
        self.group = group
        self.default_roles = set(default_roles)


# 全量 feature 清单（有序、去重）
FEATURES: list[FeatureDef] = []
_seen_keys = set()
for _k, _lbl, _grp, _roles in _FEATURES_DEF:
    if _k in _seen_keys:
        continue
    _seen_keys.add(_k)
    FEATURES.append(FeatureDef(_k, _lbl, _grp, _roles))

FEATURE_BY_KEY: dict[str, FeatureDef] = {f.key: f for f in FEATURES}


def all_feature_keys() -> list[str]:
    return [f.key for f in FEATURES]


def default_allowed(role: UserRole, feature_key: str) -> bool:
    """根据 DEFAULT_ROLE_MATRIX 判断某角色对该 feature_key 是否默认放行。"""
    f = FEATURE_BY_KEY.get(feature_key)
    if not f:
        return False
    return role.value in f.default_roles
