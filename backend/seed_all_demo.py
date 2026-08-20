"""SEMS 全模块测试数据生成脚本。

为 SEMS（半导体设备管理系统）的全部模块生成完整测试数据，
确保所有看板和列表页（包括不同角色的看板）都有数据可看。

运行方式:
    cd backend && .venv/bin/python seed_all_demo.py

覆盖模块:
  基础数据:   User / Equipment / EquipmentStatusLog / EquipmentAttachment
  支撑资源:   SparePart / EquipmentSparePart / SparePartMovement / SparePartUsage
  日常运维:   InspectionTemplate / InspectionItem / InspectionRecord / InspectionResult
              WorkOrder / RepairReport(+FiveWhy)
  工艺文控:   ProcessDocument / FormTemplate / FormRecord(+Value) / FormRecordAmendment
  合规安全:   SafetyInspection
  生命周期:   EquipmentLifecycle
  润滑管理:   LubricationPoint / LubricationRecord
  数据价值:   KnowledgeEntry / EquipmentCost

注意:
  - passlib 在当前环境与 bcrypt 5.x 不兼容，改用 app.services.user_service.get_password_hash
  - FormRecordAmendment 模型无 status 列，待审批状态用 approved=None 表示（NULL=待批）
  - LubricationPoint 列名为 next_lubrication_date（非 next_lubricated_date）
"""
import os
import sys
import uuid
import random
import pathlib
from datetime import datetime, timedelta
from decimal import Decimal

# 确保 backend 目录在 path
os.chdir(pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, ".")

from app.core.database import SessionLocal, engine, Base
from app.models import (
    User, UserRole, Equipment, EquipmentStatus, EquipmentStatusLog,
    EquipmentAttachment, SparePart, EquipmentSparePart, SparePartMovement,
    SparePartUsage, InspectionTemplate, InspectionItem, InspectionRecord,
    InspectionResult, WorkOrder, WorkOrderType, WorkOrderStatus, FaultCategory,
    RepairReport, FiveWhy, ProcessDocument, FormTemplate, FormRecord,
    FormRecordValue, FormRecordAmendment, SafetyInspection,
    EquipmentLifecycle, LubricationPoint, LubricationRecord,
    KnowledgeEntry, EquipmentCost, D8Report, D8Status,
)
from app.services.user_service import get_password_hash

random.seed(42)
NOW = datetime.now()


# =====================================================================
#  1. 用户（6 种角色各至少 1 个）
# =====================================================================

def _seed_users(db):
    print(">>> 创建用户...")
    defs = [
        ("admin",       "管理员",   UserRole.ADMIN,            "admin123"),
        ("engineer1",   "张工",     UserRole.ENGINEER,         "eng123"),
        ("engineer2",   "李工",     UserRole.ENGINEER,         "eng123"),
        ("process1",    "周工艺",   UserRole.PROCESS_ENGINEER, "proc123"),
        ("qa1",         "陈品管",   UserRole.QA,               "qa123"),
        ("prod_mgr1",   "吴主管",   UserRole.PRODUCTION_MANAGER, "pm123"),
        ("leader1",     "钱班长",   UserRole.TEAM_LEADER,      "tl123"),
        ("operator1",   "王操作",   UserRole.OPERATOR,         "op123"),
        ("operator2",   "赵操作",   UserRole.OPERATOR,         "op123"),
        ("viewer1",     "孙查看",   UserRole.VIEWER,            "view123"),
    ]
    users = {}
    for username, full_name, role, pwd in defs:
        u = User(
            username=username,
            full_name=full_name,
            hashed_password=get_password_hash(pwd),
            role=role,
            is_active=True,
            must_change_password=False,
            last_password_changed_at=NOW - timedelta(days=30),
        )
        db.add(u)
        users[username] = u
    db.flush()
    print(f"    + 用户: {len(users)} 个（覆盖 6 种角色）")
    return users


# =====================================================================
#  2. 设备（10 台，覆盖各种状态 / 厂区 / 区域）
# =====================================================================

def _seed_equipment(db):
    print(">>> 创建设备...")
    defs = [
        # name, asset_no, factory, area, model, vendor, status
        ("PVD-S200 真空镀膜机",   "EQ-FAB1-001", "FAB1", "洁净室", "PVD-S200",     "AMAT",   EquipmentStatus.RUN),
        ("ASML-1400 光刻机",      "EQ-FAB1-002", "FAB1", "洁净室", "PAS-1400",     "ASML",   EquipmentStatus.IDLE),
        ("AMAT-9800 刻蚀机",      "EQ-FAB1-003", "FAB1", "洁净室", "AMAT-9800",    "AMAT",   EquipmentStatus.DOWN),
        ("DNS-3000 晶圆清洗机",   "EQ-FAB1-004", "FAB1", "洁净室", "DNS-3000",     "DNS",    EquipmentStatus.PM),
        ("AMAT CVD 镀膜机",       "EQ-FAB1-005", "FAB1", "洁净室", "AMAT-CVD-2",   "AMAT",   EquipmentStatus.ENGINEERING),
        ("TEL CLEAN 涂胶显影机",  "EQ-FAB2-001", "FAB2", "洁净室", "TEL-CLEAN-8",  "TEL",    EquipmentStatus.PROCESS_VALIDATION),
        ("DNS-3000B 晶圆清洗机",  "EQ-FAB2-002", "FAB2", "洁净室", "DNS-3000B",    "DNS",    EquipmentStatus.RUN),
        ("空压机 Atlas-200",      "EQ-FAB1-006", "FAB1", "动力区", "Atlas-GA-200", "Atlas",  EquipmentStatus.RUN),
        ("冷水机组 Trane-500",    "EQ-FAB1-007", "FAB1", "辅助区", "Trane-500",    "Trane",  EquipmentStatus.IDLE),
        ("纯水系统 GE-1000",      "EQ-FAB2-003", "FAB2", "动力区", "GE-1000",      "GE",     EquipmentStatus.OFFLINE),
    ]
    eqs = []
    for name, asset_no, factory, area, model, vendor, status in defs:
        eq = Equipment(
            name=name, asset_no=asset_no, factory=factory, area=area,
            model=model, vendor=vendor, serial_no=f"SN-{asset_no}",
            install_date=NOW - timedelta(days=random.randint(365, 1800)),
            theoretical_cycle=round(random.uniform(30.0, 120.0), 1),
            spec={"voltage": "380V", "power": f"{random.randint(10, 50)}kW"},
            description=f"{name}，安装于{factory} {area}",
            current_status=status,
            is_active=True,
        )
        db.add(eq)
        eqs.append(eq)
    db.flush()
    print(f"    + 设备: {len(eqs)} 台")
    return eqs


# =====================================================================
#  3. 设备状态变更日志（每台 2-3 条）
# =====================================================================

def _seed_equipment_status_logs(db, eqs, users):
    print(">>> 创建设备状态日志...")
    ops = [users["operator1"], users["operator2"], users["engineer1"]]
    reason_map = {
        EquipmentStatus.RUN: ("PRODUCTION", "正常生产启动"),
        EquipmentStatus.IDLE: ("NO_WIP", "无在制品待料"),
        EquipmentStatus.DOWN: ("FAULT", "设备故障停机"),
        EquipmentStatus.PM: ("PM_PLAN", "计划保养"),
        EquipmentStatus.ENGINEERING: ("ENG_TEST", "工程调试"),
        EquipmentStatus.PROCESS_VALIDATION: ("PV", "工艺验证中"),
        EquipmentStatus.OFFLINE: ("DISABLED", "设备停用"),
    }
    count = 0
    for eq in eqs:
        # 生成 2-3 条历史状态变更
        transitions = [
            (EquipmentStatus.OFFLINE, EquipmentStatus.IDLE),
            (EquipmentStatus.IDLE, EquipmentStatus.RUN),
        ]
        if eq.current_status != EquipmentStatus.RUN:
            transitions.append((EquipmentStatus.RUN, eq.current_status))
        elif random.random() > 0.5:
            transitions.append((EquipmentStatus.RUN, EquipmentStatus.IDLE))
            transitions.append((EquipmentStatus.IDLE, EquipmentStatus.RUN))

        base_time = NOW - timedelta(days=random.randint(3, 15))
        for i, (frm, to) in enumerate(transitions):
            start = base_time + timedelta(hours=i * 8)
            end = start + timedelta(hours=random.randint(2, 6)) if i < len(transitions) - 1 else None
            rcode, rdetail = reason_map.get(to, ("OTHER", "状态变更"))
            log = EquipmentStatusLog(
                equipment_id=eq.id,
                from_status=frm,
                to_status=to,
                start_time=start,
                end_time=end,
                duration_minutes=round((end - start).total_seconds() / 60, 1) if end else None,
                reason_code=rcode,
                reason_detail=rdetail,
                operator_id=random.choice(ops).id,
                remark="",
            )
            db.add(log)
            count += 1
    db.flush()
    print(f"    + 设备状态日志: {count} 条")
    return count


# =====================================================================
#  4. 设备附件（每台 1-2 个）
# =====================================================================

def _seed_equipment_attachments(db, eqs, users):
    print(">>> 创建设备附件...")
    admin = users["admin"]
    cats = [("SOP", "操作标准书"), ("说明书", "设备使用说明书"), ("图纸", "机械结构图"), ("其他", "验收报告")]
    count = 0
    for eq in eqs:
        n = random.randint(1, 2)
        for cat_name, desc in random.sample(cats, n):
            att = EquipmentAttachment(
                equipment_id=eq.id,
                filename=f"{eq.asset_no}_{cat_name}.pdf",
                stored_path=f"data/uploads/{eq.asset_no}_{cat_name}.pdf",
                file_size=random.randint(100_000, 5_000_000),
                file_type="application/pdf",
                category=cat_name,
                description=f"{eq.name} {desc}",
                uploaded_by=admin.id,
            )
            db.add(att)
            count += 1
    db.flush()
    print(f"    + 设备附件: {count} 条")
    return count


# =====================================================================
#  5. 备件（14 个，4 个低库存）
# =====================================================================

def _seed_spare_parts(db):
    print(">>> 创建备件...")
    defs = [
        # sku, name, spec, brand, unit, safety, current, price, location
        ("SP-001", "真空泵轴承",        "SKF-6204",        "SKF",     "个", 10, 15,  850.0,  "A-01-03"),
        ("SP-002", "温度传感器",        "PT100-A级",       "Omega",   "个", 8,  3,   320.0,  "A-02-01"),   # 低库存
        ("SP-003", "MFC质量流量计",     "MKS-1179A",       "MKS",     "个", 5,  2,   12000.0,"B-01-05"),   # 低库存
        ("SP-004", "O型密封圈",         "氟橡胶Φ50",       "Parker",  "个", 50, 80,  12.0,   "C-03-12"),
        ("SP-005", "真空泵油",          "ULTRA-15",        "Leybold", "L", 20, 25,  180.0,  "D-01-08"),
        ("SP-006", "PLC模块",           "S7-1500-CPU",     "Siemens", "个", 3,  1,   8500.0, "B-02-01"),   # 低库存
        ("SP-007", "伺服电机",          "750W-AC",         "Yaskawa", "个", 4,  6,   4200.0, "B-03-04"),
        ("SP-008", "RF匹配器",          "AMAT-9800原装",   "AMAT",    "个", 2,  4,   15000.0,"B-01-09"),
        ("SP-009", "干泵爪",            "iQDP-80备件",     "Edwards", "套", 2,  1,   6500.0, "B-04-02"),   # 低库存
        ("SP-010", "加热器",            "24V-200W",        "Watlow",  "个", 6,  10,  580.0,  "A-04-07"),
        ("SP-011", "气压过滤器",        "SMC-AW40",        "SMC",     "个", 15, 22,  85.0,   "C-01-03"),
        ("SP-012", "UV灯管",            "365nm-12kW",      "USHIO",   "个", 4,  5,   3200.0, "A-05-01"),
        ("SP-013", "冷却水接头",        "SS316-1/2in",     "Swagelok","个", 20, 30,  45.0,   "C-05-08"),
        ("SP-014", "静电卡盘",          "EQ-ESC-300",      "NTK",     "个", 1,  2,   45000.0,"B-06-01"),
    ]
    parts = []
    for sku, name, spec, brand, unit, safety, current, price, loc in defs:
        p = SparePart(
            sku=sku, name=name, spec=spec, brand=brand, unit=unit,
            safety_stock=safety, current_stock=current,
            unit_price=price, location=loc,
            remark="",
        )
        db.add(p)
        parts.append(p)
    db.flush()
    low = sum(1 for p in parts if p.current_stock < p.safety_stock)
    print(f"    + 备件: {len(parts)} 个（低库存 {low} 个）")
    return parts


# =====================================================================
#  6. 设备-易损件关联
# =====================================================================

def _seed_equipment_spare_parts(db, eqs, parts):
    print(">>> 创建设备-易损件关联...")
    count = 0
    for eq in eqs[:8]:
        chosen = random.sample(parts, random.randint(2, 4))
        for p in chosen:
            db.add(EquipmentSparePart(
                equipment_id=eq.id,
                spare_part_id=p.id,
                qty_per=random.randint(1, 3),
                remark="",
            ))
            count += 1
    db.flush()
    print(f"    + 设备-易损件关联: {count} 条")
    return count


# =====================================================================
#  7. 备件出入库记录（每个 2-3 条）
# =====================================================================

def _seed_spare_part_movements(db, parts, users):
    print(">>> 创建备件出入库记录...")
    ops = [users["operator1"], users["operator2"], users["engineer1"]]
    count = 0
    for p in parts:
        # 入库记录（初始化）
        db.add(SparePartMovement(
            spare_part_id=p.id, movement_type="IN", qty=p.current_stock + 5,
            before_stock=0, after_stock=p.current_stock + 5,
            ref_type="INIT", ref_id=None,
            operator_id=random.choice(ops).id,
            remark="初始入库",
            created_at=NOW - timedelta(days=random.randint(30, 90)),
        ))
        count += 1
        # 出库记录
        db.add(SparePartMovement(
            spare_part_id=p.id, movement_type="OUT", qty=5,
            before_stock=p.current_stock + 5, after_stock=p.current_stock,
            ref_type="MANUAL", ref_id=None,
            operator_id=random.choice(ops).id,
            remark="日常领用",
            created_at=NOW - timedelta(days=random.randint(5, 25)),
        ))
        count += 1
        # 调整记录（部分）
        if random.random() > 0.5:
            db.add(SparePartMovement(
                spare_part_id=p.id, movement_type="ADJUST", qty=1,
                before_stock=p.current_stock, after_stock=p.current_stock,
                ref_type="MANUAL", ref_id=None,
                operator_id=random.choice(ops).id,
                remark="盘点调整",
                created_at=NOW - timedelta(days=random.randint(1, 5)),
            ))
            count += 1
    db.flush()
    print(f"    + 备件出入库记录: {count} 条")
    return count


# =====================================================================
#  8. 点检模板 + 检查项
# =====================================================================

def _seed_inspection_templates(db, eqs):
    print(">>> 创建点检模板+检查项...")
    defs = [
        ("洁净室设备日点检",   "DAILY",   "每日开机前点检",
         [("真空度检查", "≤5E-6 Torr"), ("冷却水流量", "≥3 L/min"),
          ("温度检查", "25±2℃"), ("气体压力", "0.3±0.05 MPa"),
          ("报警灯测试", "功能正常"), ("外观清洁", "无异物")]),
        ("设备周点检",        "WEEKLY",  "每周深度点检",
         [("润滑油位", "在刻度线内"), ("皮带张力", "标准值"),
          ("电气接线", "无松动"), ("过滤器压差", "＜0.05 MPa")]),
        ("设备月度保养点检",   "MONTHLY", "月度PM保养点检",
         [("精度校准", "在公差内"), ("安全联锁测试", "功能正常"),
          ("地线电阻", "＜4Ω"), ("记录仪数据", "正常"),
          ("紧固件检查", "无松动")]),
        ("动力设备日检",       "DAILY",   "动力区设备每日巡检",
         [("运行声音", "无异常"), ("振动检查", "正常"),
          ("电流电压", "在额定范围"), ("温度检查", "＜60℃")]),
    ]
    templates = []
    item_count = 0
    for name, freq, desc, items in defs:
        eq = eqs[0] if "洁净" in name else (eqs[7] if "动力" in name else eqs[1])
        tpl = InspectionTemplate(
            name=name, equipment_id=eq.id, frequency=freq,
            is_active=True, description=desc,
        )
        db.add(tpl)
        db.flush()
        for seq, (iname, std) in enumerate(items, 1):
            db.add(InspectionItem(
                template_id=tpl.id, seq=seq,
                name=iname, standard=std, required=True,
            ))
            item_count += 1
        templates.append(tpl)
    db.flush()
    print(f"    + 点检模板: {len(templates)} 个，检查项: {item_count} 个")
    return templates


# =====================================================================
#  9. 点检记录 + 逐项结果
# =====================================================================

def _seed_inspection_records(db, templates, eqs, users):
    print(">>> 创建点检记录+结果...")
    inspectors = [users["operator1"], users["operator2"]]
    shifts = ["A", "B", "C"]
    count = 0
    result_count = 0
    for i in range(6):
        tpl = templates[i % len(templates)]
        eq = tpl.equipment_id and eqs[0] or eqs[i % len(eqs)]
        # 关联模板对应的设备
        eq = next((e for e in eqs if e.id == tpl.equipment_id), eqs[0])
        is_ng = i == 2  # 第3条为NG
        rec = InspectionRecord(
            template_id=tpl.id,
            equipment_id=eq.id,
            shift=shifts[i % 3],
            inspect_time=NOW - timedelta(days=i, hours=random.randint(0, 8)),
            inspector_id=random.choice(inspectors).id,
            overall_result="NG" if is_ng else "OK",
            remark="温度偏高，需复检" if is_ng else "",
        )
        db.add(rec)
        db.flush()
        items = db.query(InspectionItem).filter(InspectionItem.template_id == tpl.id).all()
        for item in items:
            result = "NG" if (is_ng and item.seq == 2) else "OK"
            val = "3.2 L/min" if "流量" in item.name else ("28.5℃" if "温度" in item.name else None)
            db.add(InspectionResult(
                record_id=rec.id, item_id=item.id,
                item_name=item.name, result=result,
                value=val, remark="" if result == "OK" else "超出标准",
            ))
            result_count += 1
        count += 1
    db.flush()
    print(f"    + 点检记录: {count} 条，逐项结果: {result_count} 条")
    return count


# =====================================================================
#  10. 工单（12 条，覆盖各种状态/类型，部分 SLA 超期）
# =====================================================================

def _seed_work_orders(db, eqs, users):
    print(">>> 创建工单...")
    eng1 = users["engineer1"]
    eng2 = users["engineer2"]
    op1 = users["operator1"]
    today_str = NOW.strftime("%Y%m%d")

    defs = [
        # seq, type, status, eq_idx, title, desc, assignee, urgency, sla_breach, fault_cat, root_cause, solution, prevention, days_ago_start, days_ago_end
        (1,  WorkOrderType.PM,     WorkOrderStatus.COMPLETED,     0, "PVD-S200 季度PM保养",       "按PM计划执行：清洁腔体、润滑导轨、校准真空计", eng1, "NORMAL",  False, None, None, None, None, 20, 18),
        (2,  WorkOrderType.PM,     WorkOrderStatus.COMPLETED,     6, "空压机 月度PM保养",          "更换油气分离器、检查皮带张力", eng2, "NORMAL",  False, None, None, None, None, 15, 14),
        (3,  WorkOrderType.PM,     WorkOrderStatus.IN_PROGRESS,   3, "DNS-3000 月度PM保养",        "清洁喷淋臂、校准流量计、更换过滤器", eng1, "NORMAL",  False, None, None, None, None, 1, None),
        (4,  WorkOrderType.PM,     WorkOrderStatus.PENDING_REVIEW,1, "光刻机 周PM保养",            "清洁光学镜片、检查对准精度", eng2, "NORMAL",  False, None, None, None, None, 2, 1),
        (5,  WorkOrderType.REPAIR, WorkOrderStatus.COMPLETED,     2, "刻蚀机 真空泵异常噪音",      "设备运行时发出金属摩擦声，真空度异常下降", eng1, "HIGH",   True,  FaultCategory.MECHANICAL, "轴承磨损严重", "更换真空泵轴承SKF-6204，抽真空测试正常", "建立轴承寿命台账，到期预防性更换", 10, 8),
        (6,  WorkOrderType.REPAIR, WorkOrderStatus.COMPLETED,     4, "CVD镀膜机 温度控制偏差",     "温控显示偏差超过±5℃，影响薄膜均匀性", eng2, "NORMAL", False, FaultCategory.ELECTRICAL, "温度传感器老化漂移", "更换PT100传感器并重新校准", "建立传感器寿命台账，到期更换", 8, 7),
        (7,  WorkOrderType.REPAIR, WorkOrderStatus.IN_PROGRESS,   0, "PVD-S200 RF功率不稳定",     "RF generator功率波动，导致镀膜速率不稳", eng1, "HIGH",   False, FaultCategory.ELECTRICAL, "排查中：怀疑RF匹配器老化", None, None, 1, None),
        (8,  WorkOrderType.REPAIR, WorkOrderStatus.PENDING_REVIEW,5, "涂胶显影机 通讯超时",        "与MES通讯中断，无法下载配方", op1, "NORMAL",  False, FaultCategory.SOFTWARE, "PLC固件bug", "升级PLC固件至V3.2，通讯恢复", "加强固件版本管理", 3, 2),
        (9,  WorkOrderType.REPAIR, WorkOrderStatus.ASSIGNED,      2, "刻蚀机 气压不稳定",          "工艺气体压力波动，MFC报警", eng2, "HIGH",   True,  FaultCategory.MECHANICAL, "气体过滤器堵塞", None, None, 0, None),
        (10, WorkOrderType.REPAIR, WorkOrderStatus.CREATED,       6, "空压机 排气温度偏高",        "排气温度达95℃，超过报警阈值", None, "NORMAL", False, None, None, None, None, 0, None),
        (11, WorkOrderType.PM,     WorkOrderStatus.CREATED,       7, "冷水机组 月度PM",            "计划保养：清洗冷凝器、检查制冷剂压力", op1, "LOW",    False, None, None, None, None, 0, None),
        (12, WorkOrderType.REPAIR, WorkOrderStatus.COMPLETED,     9, "纯水系统 水质异常",          "TOC指标超标，影响清洗效果", eng1, "CRITICAL", True, FaultCategory.CONSUMABLE, "活性炭滤芯失效", "更换活性炭滤芯，TOC恢复正常", "缩短滤芯更换周期", 5, 4),
    ]

    work_orders = []
    for seq, wtype, status, eq_idx, title, desc, assignee, urgency, breach, \
            fcat, rcause, sol, prev, d_start, d_end in defs:
        eq = eqs[eq_idx]
        planned_start = NOW - timedelta(days=d_start)
        actual_start = planned_start + timedelta(hours=1) if status != WorkOrderStatus.CREATED else None
        actual_end = NOW - timedelta(days=d_end) if d_end is not None else None
        completed_at = actual_end if status == WorkOrderStatus.COMPLETED else None

        # SLA
        sla_resp = 60 if wtype == WorkOrderType.REPAIR else 240
        sla_res = 480 if wtype == WorkOrderType.REPAIR else 720
        actual_resp = random.randint(30, 55) if actual_start else None
        actual_res = None
        if completed_at and actual_start:
            actual_res = int((completed_at - (NOW - timedelta(days=d_start))).total_seconds() / 60)

        wo = WorkOrder(
            order_no=f"WO-{today_str}-{seq:03d}",
            type=wtype, status=status,
            equipment_id=eq.id,
            title=title, description=desc,
            assignee_id=assignee.id if assignee else None,
            urgency=urgency,
            fault_category=fcat,
            root_cause=rcause, solution=sol, prevention=prev,
            planned_start=planned_start,
            planned_end=planned_start + timedelta(hours=8),
            actual_start=actual_start,
            actual_end=actual_end,
            completed_at=completed_at,
            sla_response_minutes=sla_resp,
            sla_resolution_minutes=sla_res,
            actual_response_minutes=actual_resp,
            actual_resolution_minutes=actual_res if actual_res and actual_res > 0 else None,
            sla_breach=breach,
            escalated=breach,
            escalated_to_id=users["admin"].id if breach else None,
            escalated_at=NOW - timedelta(days=d_start - 1) if breach else None,
            remark="",
        )
        db.add(wo)
        work_orders.append(wo)
    db.flush()
    breached = sum(1 for w in work_orders if w.sla_breach)
    print(f"    + 工单: {len(work_orders)} 条（SLA 超期 {breached} 条）")
    return work_orders


# =====================================================================
#  11. 报修单 + FiveWhy 分析（关联 REPAIR 工单）
# =====================================================================

def _seed_repair_reports_and_five_whys(db, eqs, users, work_orders):
    print(">>> 创建报修单+FiveWhy分析...")
    ops = [users["operator1"], users["operator2"]]
    repair_wos = [w for w in work_orders if w.type == WorkOrderType.REPAIR]
    count = 0
    five_count = 0
    for wo in repair_wos[:5]:
        rpt = RepairReport(
            equipment_id=wo.equipment_id,
            reporter_id=random.choice(ops).id,
            phenomenon=wo.description or wo.title,
            urgency=wo.urgency,
            reported_at=wo.created_at - timedelta(hours=2),
            work_order_id=wo.id,
            status="CONVERTED" if wo.status != WorkOrderStatus.CREATED else "OPEN",
        )
        db.add(rpt)
        count += 1
        wo.source_report_id = rpt.id

        # FiveWhy 分析
        qs = [
            "为什么设备会出现该故障？",
            "为什么部件会磨损/老化？",
            "为什么没有提前发现？",
            "为什么保养周期不够？",
            "如何从制度上预防再发生？",
        ]
        ans = [
            "部件磨损/老化导致",
            "长期高频运行，未及时更换",
            "点检项目未覆盖该部件",
            "保养周期设置偏长",
            "建立动态保养周期模型+寿命台账",
        ]
        for i, (q, a) in enumerate(zip(qs, ans), 1):
            db.add(FiveWhy(
                work_order_id=wo.id, seq=i,
                question=q, answer=a,
            ))
            five_count += 1
    db.flush()
    print(f"    + 报修单: {count} 条，FiveWhy: {five_count} 条")
    return count


# =====================================================================
#  12. 备件领用（关联工单）
# =====================================================================

def _seed_spare_part_usages(db, parts, work_orders, users):
    print(">>> 创建备件领用记录...")
    completed_repair = [w for w in work_orders if w.type == WorkOrderType.REPAIR and w.status == WorkOrderStatus.COMPLETED]
    ops = [users["engineer1"], users["engineer2"]]
    count = 0
    for wo in completed_repair[:4]:
        p = random.choice(parts)
        qty = random.randint(1, 2)
        before = p.current_stock
        p.current_stock = max(0, p.current_stock - qty)
        mv = SparePartMovement(
            spare_part_id=p.id, movement_type="OUT", qty=qty,
            before_stock=before, after_stock=p.current_stock,
            ref_type="WORK_ORDER", ref_id=wo.id,
            operator_id=wo.assignee_id or random.choice(ops).id,
            remark=f"工单领用: {wo.order_no}",
            created_at=wo.actual_start or NOW,
        )
        db.add(mv)
        db.flush()
        db.add(SparePartUsage(
            work_order_id=wo.id, spare_part_id=p.id, qty=qty,
            movement_id=mv.id, remark="维修领用",
        ))
        count += 1
    db.flush()
    print(f"    + 备件领用: {count} 条")
    return count


# =====================================================================
#  13. 表单模板
# =====================================================================

def _seed_form_templates(db, eqs, users):
    print(">>> 创建表单模板...")
    pe = users["process1"]
    field_schema_1 = [
        {"key": "batch_no", "type": "text", "label": "批号", "required": True, "placeholder": "B20260801-01", "seq": 1},
        {"key": "temperature", "type": "number", "label": "腔体温度", "required": True, "unit": "℃", "min": 20, "max": 300, "seq": 2},
        {"key": "pressure", "type": "number", "label": "工艺压力", "required": True, "unit": "Torr", "seq": 3},
        {"key": "result", "type": "radio", "label": "检验结果", "required": True,
         "options": [{"label": "合格", "value": "pass"}, {"label": "不合格", "value": "fail"}], "seq": 4},
        {"key": "remark", "type": "textarea", "label": "备注", "required": False, "seq": 5},
    ]
    field_schema_2 = [
        {"key": "shift", "type": "select", "label": "班次", "required": True,
         "options": [{"label": "A班", "value": "A"}, {"label": "B班", "value": "B"}, {"label": "C班", "value": "C"}], "seq": 1},
        {"key": "operator", "type": "text", "label": "操作员", "required": True, "seq": 2},
        {"key": "run_qty", "type": "number", "label": "运行数量", "required": True, "unit": "片", "seq": 3},
        {"key": "defect_qty", "type": "number", "label": "不良数量", "required": True, "unit": "片", "seq": 4},
        {"key": "handover_note", "type": "textarea", "label": "交接事项", "required": False, "seq": 5},
    ]
    field_schema_3 = [
        {"key": "inspect_date", "type": "date", "label": "检查日期", "required": True, "seq": 1},
        {"key": "safety_interlock", "type": "boolean", "label": "安全联锁功能", "required": True, "seq": 2},
        {"key": "emergency_stop", "type": "boolean", "label": "急停按钮", "required": True, "seq": 3},
        {"key": "grounding", "type": "radio", "label": "接地检查",
         "options": [{"label": "正常", "value": "ok"}, {"label": "异常", "value": "ng"}], "required": True, "seq": 4},
        {"key": "findings", "type": "textarea", "label": "检查发现", "required": False, "seq": 5},
    ]
    tpls = [
        FormTemplate(name="工艺参数记录表", code="FORM-PROCESS-01", category="record",
                     equipment_id=eqs[0].id, description="PVD镀膜工艺参数记录",
                     field_schema=field_schema_1, is_active=True, created_by=pe.id),
        FormTemplate(name="交接班记录表", code="FORM-SHIFT-01", category="record",
                     equipment_id=None, description="通用班次交接记录",
                     field_schema=field_schema_2, is_active=True, created_by=pe.id),
        FormTemplate(name="设备安全检查表", code="FORM-SAFETY-01", category="guide",
                     equipment_id=None, description="设备安全检查通用表单",
                     field_schema=field_schema_3, is_active=True, created_by=pe.id),
    ]
    for t in tpls:
        db.add(t)
    db.flush()
    print(f"    + 表单模板: {len(tpls)} 个")
    return tpls


# =====================================================================
#  14. 表单记录 + 字段值（含已提交待审核）
# =====================================================================

def _seed_form_records(db, templates, eqs, users):
    print(">>> 创建表单记录+字段值...")
    op1 = users["operator1"]
    op2 = users["operator2"]
    qa = users["qa1"]

    # (tpl_idx, eq_idx, status, audited, batch, shift, days_ago)
    defs = [
        (0, 0, "已提交", False, "B20260805-01", "A", 5),   # 待审核
        (0, 6, "已提交", False, "B20260806-01", "B", 4),   # 待审核
        (0, 3, "已审核", True,  "B20260728-02", "A", 12),
        (1, 0, "已审核", True,  None,            "A", 3),
        (1, 2, "草稿",   False, None,            "B", 1),
        (2, 0, "已审核", True,  None,            None, 7),
        (2, 2, "已作废", False, None,            None, 15),
    ]
    records = []
    val_count = 0
    for tpl_idx, eq_idx, status, audited, batch, shift, days_ago in defs:
        tpl = templates[tpl_idx]
        eq = eqs[eq_idx]
        filled_by = op1 if tpl_idx == 0 else op2
        prod_date = NOW - timedelta(days=days_ago)
        rec = FormRecord(
            template_id=tpl.id,
            title=f"{tpl.name}_{prod_date.strftime('%Y%m%d')}_{eq.asset_no}",
            equipment_id=eq.id,
            batch_no=batch,
            shift=shift,
            production_date=prod_date,
            status=status,
            filled_by=filled_by.id,
            submitted_at=prod_date if status != "草稿" else None,
            submitted_by=filled_by.id if status != "草稿" else None,
            audited=audited,
            audited_at=prod_date + timedelta(hours=2) if audited else None,
            audited_by=qa.id if audited else None,
            remark="",
        )
        db.add(rec)
        db.flush()

        # 填充字段值
        sample_values = {
            "batch_no": batch or f"B{prod_date.strftime('%Y%m%d')}-01",
            "temperature": 180.5,
            "pressure": 0.0008,
            "result": "pass",
            "remark": "生产正常",
            "shift": shift or "A",
            "operator": filled_by.full_name,
            "run_qty": 350,
            "defect_qty": 5,
            "handover_note": "设备运行正常，注意真空泵温度",
            "inspect_date": prod_date.strftime("%Y-%m-%d"),
            "safety_interlock": True,
            "emergency_stop": True,
            "grounding": "ok",
            "findings": "各项检查正常",
        }
        for field in tpl.field_schema:
            key = field["key"]
            val = sample_values.get(key)
            if val is not None:
                db.add(FormRecordValue(
                    record_id=rec.id,
                    field_key=key,
                    field_label_snapshot=field.get("label", key),
                    field_value=val,
                ))
                val_count += 1
        records.append(rec)
    db.flush()
    pending = sum(1 for r in records if r.status == "已提交" and not r.audited)
    print(f"    + 表单记录: {len(records)} 条，字段值: {val_count} 条（待审核 {pending} 条）")
    return records


# =====================================================================
#  15. 表单修正记录（待审批：approved=None）
# =====================================================================

def _seed_form_record_amendments(db, records, users):
    print(">>> 创建表单修正记录...")
    # 注：FormRecordAmendment 无 status 列，待审批用 approved=None 表示（NULL=待批）
    audited_recs = [r for r in records if r.audited]
    if len(audited_recs) < 2:
        db.flush()
        print("    + 表单修正记录: 0 条（无已审核记录可用）")
        return 0
    op1 = users["operator1"]
    qa = users["qa1"]
    import hashlib
    count = 0
    for rec in audited_recs[:2]:
        sig = hashlib.sha256(f"{rec.id}|amend|{op1.id}|{NOW.isoformat()}|true".encode()).hexdigest()
        amend = FormRecordAmendment(
            record_id=rec.id,
            field_key="defect_qty" if "defect_qty" in [f["key"] for f in rec.template.field_schema] else "remark",
            field_label="不良数量" if random.random() > 0.5 else "备注",
            original_value=5,
            corrected_value=3,
            reason="复检后发现2片误判，实际不良为3片",
            amended_by_id=op1.id,
            amended_by_username=op1.username,
            amended_at=NOW - timedelta(days=1),
            amendment_signature=sig,
            password_validated=True,
            approved=None,        # NULL = 待批（pending）
            approved_by_id=None,
            approved_at=None,
        )
        db.add(amend)
        count += 1
    db.flush()
    print(f"    + 表单修正记录: {count} 条（approved=None 表示待审批）")
    return count


# =====================================================================
#  16. 工艺文件（14 个，覆盖草稿/审核中/生效/作废）
# =====================================================================

def _seed_process_documents(db, eqs, users):
    print(">>> 创建工艺文件...")
    pe = users["process1"]
    eng = users["engineer1"]
    qa = users["qa1"]

    # (doc_no, doc_class, doc_name, doc_type, category, version, status, eq_idx, uploaded_by,
    #  effective_date_offset, review_cycle, next_review_offset, description)
    defs = [
        ("SOP-EQ-001",  "SOP",   "PVD真空镀膜机标准作业程序", "Recipe",    "guide",  "V1.2", "生效",   0, pe, -380, 12, -15,  "标准生产配方"),
        ("SOP-EQ-002",  "SOP",   "光刻机标准作业程序",        "Recipe",    "guide",  "V2.0", "生效",   1, pe, -355, 12, 10,   "工序流程定义"),
        ("SIP-QA-001",  "SIP",   "PVD镀膜膜厚检验规范",       "Spec",      "guide",  "V1.0", "审核中", 0, pe, None,  None, None, "膜厚检验SIP"),
        ("SIP-QA-002",  "SIP",   "刻蚀均匀性检验规范",        "Spec",      "guide",  "V1.1", "审核中", 2, pe, None,  None, None, "刻蚀均匀性SIP"),
        ("SIP-QA-003",  "SIP",   "清洗洁净度检验规范",        "Spec",      "guide",  "V1.0", "审核中", 3, pe, None,  None, None, "清洗洁净度SIP"),
        ("SPEC-ENG-001","SPEC",  "PVD设备工艺规格书",         "Spec",      "guide",  "V1.0", "生效",   0, eng,-200,  None, None, "工艺参数规格书"),
        ("SPEC-ENG-002","SPEC",  "CVD镀膜工艺规格书(草稿)",   "Spec",      "guide",  "V0.9", "草稿",   4, pe, None,  None, None, "工艺员编制中"),
        ("SPEC-ENG-003","SPEC",  "旧版刻蚀工艺规格书",        "Spec",      "guide",  "V1.0", "作废",   2, eng,-500,  None, None, "已被V2.0替代"),
        ("SOP-EQ-003",  "SOP",   "晶圆清洗机标准作业程序",    "Recipe",    "guide",  "V1.3", "生效",   3, pe, -360, 12, 5,    "清洗工艺配方"),
        ("SOP-EQ-004",  "SOP",   "涂胶显影机标准作业程序",    "Recipe",    "guide",  "V1.1", "草稿",   5, pe, None,  None, None, "编制中"),
        ("FORM-OP-001", "FORM",  "工艺参数记录表模板",        "其他",      "guide",  "V1.0", "生效",   0, pe, -365, 12, 0,    "结构化表单模板"),
        ("RECORD-OP-001","RECORD","PVD批次记录_20260805",    "BatchRecord","record","V1",   "草稿",   0, pe, None,  None, None, "批次作业记录"),
        ("RECORD-OP-002","RECORD","清洗批次记录_20260806",   "BatchRecord","record","V1",   "生效",   3, pe, -4,   None, None, "批次作业记录"),
        ("EXTERN-001",  "EXTERN", "客户提供的工艺规范",       "Spec",      "guide",  "V1.0", "生效",   1, qa, -100, 12, 20,   "客户外部文件"),
    ]

    count = 0
    review_due = 0
    pending_review = 0
    for doc_no, doc_class, doc_name, doc_type, category, version, status, eq_idx, uploader, \
            eff_offset, review_cycle, nr_offset, desc in defs:
        eq = eqs[eq_idx]
        eff_date = NOW + timedelta(days=eff_offset) if eff_offset is not None else None
        next_review = NOW + timedelta(days=nr_offset) if nr_offset is not None else None
        doc = ProcessDocument(
            equipment_id=eq.id,
            category=category,
            doc_no=doc_no,
            doc_class=doc_class,
            doc_name=doc_name,
            doc_type=doc_type,
            version=version,
            version_seq=1,
            group_id=uuid.uuid4().hex,
            is_latest=True,
            status=status,
            effective_date=eff_date,
            review_cycle_month=review_cycle,
            next_review_date=next_review,
            stored_path=f"data/process_docs/{doc_no}.pdf",
            file_size=random.randint(50_000, 2_000_000),
            file_type="application/pdf",
            description=desc,
            uploaded_by=uploader.id,
            source_type="CUSTOMER" if doc_class == "EXTERN" else None,
            source_ref_no=f"CUST-SPEC-{doc_no}" if doc_class == "EXTERN" else None,
            received_date=eff_date if doc_class == "EXTERN" else None,
        )
        db.add(doc)
        count += 1
        if status == "审核中":
            pending_review += 1
        if status == "生效" and next_review is not None and next_review <= NOW + timedelta(days=30):
            review_due += 1
    db.flush()
    print(f"    + 工艺文件: {count} 条（审核中 {pending_review}，复审到期 {review_due}）")
    return count


# =====================================================================
#  17. 安全检查（12 条，覆盖 4 种类型）
# =====================================================================

def _seed_safety_inspections(db, eqs, users):
    print(">>> 创建安全检查记录...")
    eng = users["engineer1"]
    op = users["operator1"]

    # (eq_idx, check_type, check_name, standard, frequency, last_offset, next_offset, result, cert_no, cert_expiry_offset, findings, corrective)
    defs = [
        (0, "safety_device",      "安全光幕功能测试",     "遮挡光幕时设备应立即停止",     "monthly",   -25, -5,   "pass",  None,        None,   "功能正常", None),
        (2, "safety_device",      "急停按钮测试",         "按下急停设备立即断电",         "monthly",   -28, 2,    "pending",None,       None,   "",        None),
        (3, "safety_device",      "安全门联锁检查",       "开门时设备暂停运行",           "weekly",    -5,  2,    "pass",  None,        None,   "联锁正常", None),
        (8, "special_equipment",  "空压机压力容器年检",   "按特种设备安全技术规范",       "yearly",    -350,-15,  "pass",  "SE-2026-0815", -15, "年检合格", None),
        (7, "special_equipment",  "冷水机组压力容器年检", "按特种设备安全技术规范",       "yearly",    -340, 25,  "pass",  "SE-2026-0816", 10, "年检合格", None),
        (9, "special_equipment",  "纯水系统特种设备登记", "压力容器使用登记证",           "yearly",    -360,-5,   "pending","SE-2026-0817",-5,  "证书即将到期", "需提前申请复审"),
        (0, "environmental",      "洁净室粒子数检测",     "ISO Class 5 ≤3520/m³(0.5μm)",  "weekly",    -3,  4,    "pass",  None,        None,   "粒子数达标", None),
        (4, "environmental",      "废气排放检测",         "VOC排放＜50mg/m³",             "quarterly", -80, 10,   "pass",  None,        None,   "达标排放", None),
        (2, "environmental",      "废水pH值检测",         "pH 6.5-8.5",                  "daily",     -1,  0,    "fail",  None,        None,   "pH=6.2偏低", "已加药调整"),
        (0, "fire_protection",    "灭火器有效期检查",     "压力指针在绿区",               "monthly",   -25, 5,    "pass",  None,        None,   "全部有效", None),
        (3, "fire_protection",    "消防栓水压测试",       "水压≥0.3MPa",                 "quarterly", -80, 10,   "pass",  None,        None,   "水压正常", None),
        (6, "fire_protection",    "应急照明测试",         "断电后照明≥30min",            "monthly",   -28, 2,    "pending",None,       None,   "",        None),
    ]
    count = 0
    check_due = 0
    cert_due = 0
    for eq_idx, ct, name, std, freq, last_off, next_off, result, cert_no, cert_exp_off, findings, corrective in defs:
        eq = eqs[eq_idx]
        last_date = NOW + timedelta(days=last_off)
        next_date = NOW + timedelta(days=next_off)
        cert_exp = NOW + timedelta(days=cert_exp_off) if cert_exp_off is not None else None
        si = SafetyInspection(
            equipment_id=eq.id,
            check_type=ct,
            check_name=name,
            check_standard=std,
            frequency=freq,
            last_check_date=last_date,
            next_check_date=next_date,
            result=result,
            findings=findings or None,
            corrective_action=corrective,
            checked_by_id=eng.id if result != "pending" else None,
            checked_by_name=eng.full_name if result != "pending" else None,
            certificate_no=cert_no,
            certificate_expiry=cert_exp,
        )
        db.add(si)
        count += 1
        if next_date <= NOW + timedelta(days=30):
            check_due += 1
        if cert_exp is not None and cert_exp <= NOW + timedelta(days=30):
            cert_due += 1
    db.flush()
    types = len(set(d[1] for d in defs))
    print(f"    + 安全检查: {count} 条（{types}种类型，检查到期 {check_due}，证书到期 {cert_due}）")
    return count


# =====================================================================
#  18. 设备生命周期 T0-T3（4 台设备，每阶段一条）
# =====================================================================

def _seed_equipment_lifecycle(db, eqs, users):
    print(">>> 创建设备生命周期记录...")
    eng = users["engineer1"]
    admin = users["admin"]
    target_eqs = eqs[:4]
    stages = [
        ("T0", "T0选型阶段", "URS需求分析与供应商评估", "选型评估"),
        ("T1", "T1采购阶段", "采购订单下达与交货跟踪", "采购执行"),
        ("T2", "T2安装调试阶段", "FAT/SAT验收与安装调试", "安装调试"),
        ("T3", "T3量产移交阶段", "量产验收与移交", "量产移交"),
    ]
    count = 0
    for eq in target_eqs:
        base_date = NOW - timedelta(days=720)
        for i, (stage, title, desc, _) in enumerate(stages):
            stage_date = base_date + timedelta(days=i * 60)
            lc = EquipmentLifecycle(
                equipment_id=eq.id,
                stage=stage,
                stage_date=stage_date,
                title=f"{eq.name} {title}",
                description=desc,
                vendor_candidates='["AMAT","Lam Research","TEL"]' if stage == "T0" else None,
                selected_vendor=eq.vendor if stage == "T0" else None,
                ur_summary="12寸晶圆制程需求，节拍≤90秒/片" if stage == "T0" else None,
                po_no=f"PO-2025-{eq.id:04d}" if stage == "T1" else None,
                po_amount=Decimal("1200000.00") if stage == "T1" else None,
                delivery_date=stage_date + timedelta(days=45) if stage == "T1" else None,
                fat_date=stage_date + timedelta(days=10) if stage == "T2" else None,
                fat_result="pass" if stage == "T2" else None,
                fat_notes="FAT各项指标达标" if stage == "T2" else None,
                sat_date=stage_date + timedelta(days=30) if stage == "T2" else None,
                sat_result="pass" if stage == "T2" else None,
                sat_notes="SAT验收通过，工艺参数达标" if stage == "T2" else None,
                commissioning_date=stage_date + timedelta(days=35) if stage == "T2" else None,
                commissioning_notes="安装调试完成，试运行正常" if stage == "T2" else None,
                handover_date=stage_date + timedelta(days=10) if stage == "T3" else None,
                handover_to=f"{eq.factory} {eq.area} 生产组" if stage == "T3" else None,
                acceptance_result="pass" if stage == "T3" else None,
                acceptance_notes="量产验收通过，正式移交生产" if stage == "T3" else None,
                attachment_path=f"data/lifecycle/{eq.asset_no}_{stage}.pdf" if stage in ("T2", "T3") else None,
                status="completed",
                created_by_id=admin.id,
            )
            db.add(lc)
            count += 1
    db.flush()
    print(f"    + 设备生命周期: {count} 条（{len(target_eqs)} 台设备 × 4 阶段）")
    return count


# =====================================================================
#  19. 润滑点（9 个，3 个到期）
# =====================================================================

def _seed_lubrication_points(db, eqs, users):
    print(">>> 创建润滑点...")
    eng = users["engineer1"]
    op = users["operator1"]

    # (eq_idx, point_name, point_code, location, person, freq, oil_type, qty, next_offset)
    defs = [
        (0, "导轨润滑点",    "LUB-001-01", "X轴导轨",     eng, "monthly",   "Mobilgrease XHP 222", "20g",  -3),   # 已过期
        (0, "真空泵油口",    "LUB-001-02", "真空泵油室",  eng, "quarterly", "ULTRA-15",            "2L",   5),    # 7天内到期
        (2, "导轨润滑点",    "LUB-003-01", "Y轴导轨",     op,  "monthly",   "Mobilgrease XHP 222", "15g",  2),    # 7天内到期
        (2, "轴承润滑点",    "LUB-003-02", "主轴轴承",    eng, "weekly",    "Klüber Isoflex Topas NB52","10g",-1),  # 已过期
        (3, "链条润滑点",    "LUB-004-01", "传动链条",    op,  "weekly",    "Chain Oil 220",       "30ml", 20),
        (6, "压缩机轴承",    "LUB-006-01", "主轴承",      eng, "quarterly", "Mobil SHC 632",       "500ml",45),
        (7, "电机轴承",      "LUB-007-01", "驱动电机",    eng, "monthly",   "SKF LGHP 2",          "30g",  60),
        (8, "泵体润滑",      "LUB-008-01", "循环泵",      op,  "monthly",   "ISO VG 46",           "1L",   30),
        (1, "导轨润滑点",    "LUB-002-01", "Z轴导轨",     eng, "monthly",   "Mobilgrease XHP 222", "20g",  15),
    ]
    points = []
    due_count = 0
    for eq_idx, name, code, loc, person, freq, oil, qty, next_off in defs:
        eq = eqs[eq_idx]
        next_date = NOW + timedelta(days=next_off)
        lp = LubricationPoint(
            equipment_id=eq.id,
            point_name=name,
            point_code=code,
            fixed_location=loc,
            fixed_person_id=person.id,
            fixed_person_name=person.full_name,
            fixed_frequency=freq,
            fixed_oil_type=oil,
            fixed_quantity=qty,
            next_lubrication_date=next_date,
            enabled=True,
            remark="",
        )
        db.add(lp)
        points.append(lp)
        if next_date <= NOW + timedelta(days=7):
            due_count += 1
    db.flush()
    print(f"    + 润滑点: {len(points)} 个（7天内到期 {due_count} 个）")
    return points


# =====================================================================
#  20. 润滑执行记录
# =====================================================================

def _seed_lubrication_records(db, points, users):
    print(">>> 创建润滑执行记录...")
    eng = users["engineer1"]
    op = users["operator1"]
    count = 0
    for i, lp in enumerate(points[:5]):
        lr = LubricationRecord(
            point_id=lp.id,
            lubrication_date=NOW - timedelta(days=random.randint(5, 30)),
            oil_type_used=lp.fixed_oil_type,
            quantity_used=lp.fixed_quantity,
            performed_by_id=lp.fixed_person_id,
            performed_by_name=lp.fixed_person_name,
            result="done",
            notes="润滑执行正常" if i != 2 else "发现油液浑浊，建议下次提前更换",
        )
        db.add(lr)
        count += 1
    db.flush()
    print(f"    + 润滑执行记录: {count} 条")
    return count


# =====================================================================
#  20b. 8D 报告（4 条，含 CLOSED 可归档到知识库）
# =====================================================================

def _seed_d8_reports(db, eqs, work_orders, users):
    print(">>> 创建8D报告...")
    eng = users["engineer1"]
    qa = users["qa1"]

    repair_wos = [w for w in work_orders if w.type == WorkOrderType.REPAIR]
    data = [
        {
            "report_no": "8D-2025-001",
            "equipment": eqs[0],
            "work_order": repair_wos[0] if repair_wos else None,
            "title": "PVD-01 腔体真空异常泄漏",
            "problem": "PVD-01 在生产过程中腔体真空度突然下降至 5E-3 Torr，导致薄膜沉积均匀性超标，批次产品报废。",
            "d1_team": "张工(工程师)、王操作(操作员)、陈品管(QA)、周工艺(工艺)",
            "d2_problem_desc": "真空度在 30 分钟内从 5E-6 Torr 恶化至 5E-3 Torr，超出工艺规格 1E-5 Torr 上限。",
            "d3_interim": "立即停机，切换至备用腔体生产，隔离受影响批次产品。",
            "d4_root_cause": "O-ring 密封圈因长期高温老化失去弹性，导致腔体密封失效。",
            "d5_permanent": "更换全系列 O-ring 密封件，建立 6 个月预防性更换周期。",
            "d6_implement": "更换后真空度恢复至 3E-6 Torr，连续 72 小时生产稳定，产品合格率 99.5%。",
            "d7_prevent": "在 PM 计划中增加 O-ring 弹性测试项，建立真空度趋势监控报警。",
            "d8_recognition": "感谢团队快速响应，24 小时内恢复生产。",
            "status": D8Status.CLOSED,
            "owner": eng,
        },
        {
            "report_no": "8D-2025-002",
            "equipment": eqs[2] if len(eqs) > 2 else eqs[0],
            "work_order": repair_wos[1] if len(repair_wos) > 1 else None,
            "title": "刻蚀机温控系统漂移导致刻蚀速率偏移",
            "problem": "ETCH-02 温控传感器读数漂移 ±2°C，刻蚀速率偏差 > 8%，超出规格 ±3%。",
            "d1_team": "张工(工程师)、李工(设备)、陈品管(QA)",
            "d2_problem_desc": "温控系统 RTD 传感器在 60-80°C 区间线性度下降，读数比实际值偏高 1.5-2°C。",
            "d3_interim": "临时修正温度偏移值 +5°C，加大抽检频率至每 2 小时一次。",
            "d4_root_cause": "RTD 传感器引线连接器氧化，导致接触电阻增大，形成温度补偿误差。",
            "d5_permanent": "更换 RTD 传感器及镀金连接器，增加引线防护套管。",
            "d6_implement": "更换后温控精度恢复 ±0.3°C，刻蚀速率偏差 < 1.5%，连续运行验证通过。",
            "d7_prevent": "PM 计划增加连接器接触电阻检测项，每季度清洁一次。",
            "d8_recognition": "团队通过数据趋势分析提前发现问题，避免了批量报废。",
            "status": D8Status.CLOSED,
            "owner": eng,
        },
        {
            "report_no": "8D-2025-003",
            "equipment": eqs[4] if len(eqs) > 4 else eqs[0],
            "work_order": repair_wos[2] if len(repair_wos) > 2 else None,
            "title": "清洗机喷淋压力不足导致清洗不净",
            "problem": "WET-01 喷淋压力从 3.5 bar 下降至 1.8 bar，晶圆表面颗粒残留超标。",
            "d1_team": "王操作(操作员)、张工(工程师)、周工艺(工艺)",
            "d2_problem_desc": "喷淋压力持续下降，清洗后表面颗粒 > 50 颗（规格 < 10 颗）。",
            "d3_interim": "增加一道手工清洗工序作为临时围堵。",
            "d4_root_cause": "喷淋管路过滤器堵塞，杂质积累导致流量受限。",
            "d5_permanent": "更换 5μm 过滤芯，建立 2 周更换周期。",
            "d6_implement": "更换后压力恢复 3.5 bar，表面颗粒 < 5 颗，验证通过。",
            "d7_prevent": "在点检表增加喷淋压力趋势记录，设置 2.8 bar 预警阈值。",
            "d8_recognition": "感谢操作员及时发现并上报异常。",
            "status": D8Status.CLOSED,
            "owner": qa,
        },
        {
            "report_no": "8D-2025-004",
            "equipment": eqs[1] if len(eqs) > 1 else eqs[0],
            "work_order": None,
            "title": "光刻机对准精度漂移调查（进行中）",
            "problem": "LITH-01 对准精度近期呈现缓慢漂移趋势，尚未超出规格但需关注。",
            "d1_team": "张工(工程师)、周工艺(工艺)",
            "d2_problem_desc": "对准精度在 30 天内从 ±0.1μm 漂移至 ±0.15μm（规格 ±0.2μm）。",
            "d3_interim": "增加每日对准校准频次，监控趋势。",
            "d4_root_cause": None,
            "d5_permanent": None,
            "d6_implement": None,
            "d7_prevent": None,
            "d8_recognition": None,
            "status": D8Status.IN_PROGRESS,
            "owner": eng,
        },
    ]

    reports = []
    for d in data:
        rpt = D8Report(
            report_no=d["report_no"],
            equipment_id=d["equipment"].id,
            work_order_id=d["work_order"].id if d["work_order"] else None,
            title=d["title"],
            problem=d["problem"],
            d1_team=d["d1_team"],
            d2_problem_desc=d["d2_problem_desc"],
            d3_interim=d["d3_interim"],
            d4_root_cause=d["d4_root_cause"],
            d5_permanent=d["d5_permanent"],
            d6_implement=d["d6_implement"],
            d7_prevent=d["d7_prevent"],
            d8_recognition=d["d8_recognition"],
            status=d["status"],
            owner_id=d["owner"].id,
            closed_at=NOW if d["status"] == D8Status.CLOSED else None,
        )
        db.add(rpt)
        reports.append(rpt)

    db.flush()
    print(f"    ✅ 创建 {len(reports)} 份8D报告（{sum(1 for r in reports if r.status == D8Status.CLOSED)} 条已关闭）")
    return reports


# =====================================================================
#  21. 故障知识库（7 条，2 条复发 > 0）
# =====================================================================

def _seed_knowledge_entries(db, eqs, work_orders, users):
    print(">>> 创建故障知识库条目...")
    eng = users["engineer1"]

    repair_wos = [w for w in work_orders if w.type == WorkOrderType.REPAIR and w.source_report_id]
    defs = [
        ("真空泵轴承异响故障",     "设备运行时真空泵发出金属摩擦声，真空度下降",
         "mechanical", 0, "PVD-S200",
         "轴承磨损严重导致间隙增大", "更换轴承SKF-6204，重新安装调试",
         "建立轴承寿命台账，按运行小时数预防性更换", 3),
        ("温度传感器漂移故障",     "温控显示偏差超过±5℃，薄膜均匀性变差",
         "electrical", 4, "AMAT-CVD-2",
         "PT100传感器老化导致阻值漂移", "更换PT100-A级传感器并重新校准温控系统",
         "建立传感器寿命台账，2年到期强制更换", 1),
        ("MFC质量流量计报警",      "工艺气体流量不稳，MFC频繁报警",
         "electrical", 2, "AMAT-9800",
         "MFC内部密封圈老化导致漏气", "更换密封圈并做气密性测试",
         "定期检查气路密封性", 2),
        ("PLC通讯中断故障",        "设备与MES通讯中断，无法下载配方",
         "software", 5, "TEL-CLEAN-8",
         "PLC固件版本存在已知bug", "升级PLC固件至V3.2",
         "关注厂商固件更新通知", 0),
        ("气体过滤器堵塞",         "工艺气体压力波动，MFC报警",
         "mechanical", 2, "AMAT-9800",
         "过滤器长期未更换导致堵塞", "更换气体过滤器，恢复气路通畅",
         "缩短过滤器更换周期至3个月", 1),
        ("RF匹配器功率波动",       "RF功率不稳定，镀膜速率波动大",
         "electrical", 0, "PVD-S200",
         "RF匹配器内部电容老化", "更换RF匹配器，重新调谐",
         "增加RF参数监控点检项", 0),
        ("活性炭滤芯失效",         "纯水TOC指标超标",
         "consumable", 9, "GE-1000",
         "活性炭滤芯超过使用寿命", "更换活性炭滤芯，TOC恢复正常",
         "缩短滤芯更换周期至6个月", 0),
    ]
    count = 0
    recur = 0
    for i, (title, symptom, fcat, eq_idx, model, rcause, sol, prev, recur_cnt) in enumerate(defs):
        eq = eqs[eq_idx] if eq_idx < len(eqs) else None
        ke = KnowledgeEntry(
            title=title,
            symptom=symptom,
            fault_category=fcat,
            equipment_id=eq.id if eq else None,
            equipment_model=model,
            root_cause=rcause,
            solution=sol,
            prevention=prev,
            source_work_order_id=repair_wos[i].id if i < len(repair_wos) else None,
            tags=f"{fcat},{model}",
            views=random.randint(10, 200),
            recurrence_count=recur_cnt,
            status="active",
            created_by_id=eng.id,
            created_by_name=eng.full_name,
        )
        db.add(ke)
        count += 1
        if recur_cnt > 0:
            recur += 1
    db.flush()
    print(f"    + 故障知识条目: {count} 条（复发次数>0: {recur} 条）")
    return count


# =====================================================================
#  22. 设备成本记录（每台 2-4 条，覆盖各种类型）
# =====================================================================

def _seed_equipment_costs(db, eqs, work_orders, users):
    print(">>> 创建设备成本记录...")
    eng = users["engineer1"]
    cost_types = ["procurement", "maintenance", "spare_part", "energy", "depreciation", "scrap"]
    type_descs = {
        "procurement": "设备采购",
        "maintenance": "维护保养",
        "spare_part": "备件消耗",
        "energy": "能源消耗",
        "depreciation": "折旧",
        "scrap": "报废处置",
    }
    completed_wos = [w for w in work_orders if w.status == WorkOrderStatus.COMPLETED]
    count = 0
    for eq in eqs:
        n = random.randint(2, 4)
        chosen = random.sample(cost_types, min(n, len(cost_types)))
        # 每台都有采购成本
        if "procurement" not in chosen:
            chosen[0] = "procurement"
        for ct in chosen:
            if ct == "procurement":
                amount = Decimal(str(random.randint(800_000, 3_000_000)))
            elif ct == "maintenance":
                amount = Decimal(str(random.randint(5_000, 30_000)))
            elif ct == "spare_part":
                amount = Decimal(str(random.randint(1_000, 15_000)))
            elif ct == "energy":
                amount = Decimal(str(random.randint(3_000, 12_000)))
            elif ct == "depreciation":
                amount = Decimal(str(random.randint(50_000, 200_000)))
            else:
                amount = Decimal(str(random.randint(10_000, 50_000)))

            wo = random.choice(completed_wos) if (ct in ("maintenance", "spare_part") and completed_wos) else None
            ec = EquipmentCost(
                equipment_id=eq.id,
                cost_type=ct,
                cost_date=NOW - timedelta(days=random.randint(1, 365)),
                amount=amount,
                description=f"{eq.name} {type_descs[ct]}费用",
                work_order_id=wo.id if wo and wo.equipment_id == eq.id else None,
                spare_part_id=None,
                recorded_by_id=eng.id,
                recorded_by_name=eng.full_name,
            )
            db.add(ec)
            count += 1
    db.flush()
    types_covered = len(set(db.query(EquipmentCost.cost_type).distinct().all()))
    print(f"    + 设备成本: {count} 条（覆盖 {types_covered} 种成本类型）")
    return count


# =====================================================================
#  产品 + 生产记录（为生产管理角色看板提供数据）
# =====================================================================

def _seed_products_and_production(db, eqs, users):
    """生成产品和今日/历史生产记录。"""
    print(">>> 创建产品与生产记录...")
    from app.models import Product, ProductionRecord

    products = [
        ("P-A001", "芯片A型", "5nm / 12寸", "片", 2.5),
        ("P-B002", "芯片B型", "7nm / 12寸", "片", 3.0),
        ("P-C003", "芯片C型", "14nm / 8寸", "片", 4.0),
        ("P-D004", "功率器件", "IGBT / 6寸", "片", 5.5),
        ("P-E005", "传感器芯片", "MEMS / 8寸", "片", 3.5),
    ]
    prod_objs = []
    for code, name, spec, unit, cycle in products:
        p = Product(code=code, name=name, spec=spec, unit=unit, target_cycle=cycle, is_active=True)
        db.add(p)
        prod_objs.append(p)
    db.flush()

    # 生产记录：今日 + 历史
    operator1 = users.get("operator1")
    operator2 = users.get("operator2")
    leader1 = users.get("leader1")
    prod_mgr1 = users.get("prod_mgr1")
    operators = [o for o in [operator1, operator2] if o]

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0

    # 今日在产记录（每台 RUN/IDLE 设备 1~2 条）
    running_eqs = [e for e in eqs if e.current_status in ("RUN", "IDLE", "ENGINEERING", "PROCESS_VALIDATION")]
    for i, eq in enumerate(running_eqs[:8]):
        p = prod_objs[i % len(prod_objs)]
        op = operators[i % len(operators)] if operators else None
        start = today_start + timedelta(hours=random.randint(0, now.hour), minutes=random.randint(0, 59))
        plan_qty = random.randint(800, 2000)
        input_qty = plan_qty - random.randint(0, 50)
        good_qty = input_qty - random.randint(0, 30)
        defect_qty = input_qty - good_qty
        is_finished = random.random() > 0.4

        rec = ProductionRecord(
            record_no=f"PR-T{now.strftime('%m%d')}-{i+1:03d}",
            equipment_id=eq.id,
            product_id=p.id,
            batch_no=f"B{now.strftime('%Y%m%d')}-{i+1:02d}",
            plan_qty=plan_qty,
            input_qty=input_qty,
            good_qty=good_qty,
            defect_qty=defect_qty,
            start_time=start,
            end_time=start + timedelta(minutes=random.randint(30, 180)) if is_finished else None,
            duration_minutes=float(random.randint(30, 180)) if is_finished else None,
            ideal_cycle=p.target_cycle,
            operator_id=op.id if op else None,
        )
        db.add(rec)
        count += 1

    # 历史生产记录（过去 7 天，每天 3~5 条）
    for day_offset in range(1, 8):
        day = today_start - timedelta(days=day_offset)
        for i in range(random.randint(3, 5)):
            eq = eqs[random.randint(0, len(eqs)-1)]
            p = prod_objs[random.randint(0, len(prod_objs)-1)]
            op = operators[random.randint(0, len(operators)-1)] if operators else None
            start = day + timedelta(hours=random.randint(6, 22), minutes=random.randint(0, 59))
            plan_qty = random.randint(500, 1500)
            input_qty = plan_qty - random.randint(0, 30)
            good_qty = input_qty - random.randint(0, 20)
            defect_qty = input_qty - good_qty

            rec = ProductionRecord(
                record_no=f"PR-H{day.strftime("%m%d")}-{i+1:03d}",
                equipment_id=eq.id,
                product_id=p.id,
                batch_no=f"B{day.strftime("%Y%m%d")}-{i+1:02d}",
                plan_qty=plan_qty,
                input_qty=input_qty,
                good_qty=good_qty,
                defect_qty=defect_qty,
                start_time=start,
                end_time=start + timedelta(minutes=random.randint(60, 240)),
                duration_minutes=float(random.randint(60, 240)),
                ideal_cycle=p.target_cycle,
                operator_id=op.id if op else None,
            )
            db.add(rec)
            count += 1

    db.flush()
    print(f"    + 产品: {len(prod_objs)} 个, 生产记录: {count} 条（今日: ~{len(running_eqs[:8])} 条）")
    return prod_objs


def _seed_production_management(db, prod_objs, eqs, users):
    """生成生产管理模块测试数据：工序路由、生产订单、派工、报工。"""
    print(">>> 创建生产管理模块数据...")
    from app.models import (
        Routing, RoutingStep, RoutingStatus,
        ProductionOrder, ProductionOrderStatus, MOSourceType,
        Dispatch, DispatchStatus, LaborReport,
    )
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. 工序路由（前3个产品各1个生效版本）
    routing_steps_def = [
        [("10", "清洗", 5.0, 120), ("20", "光刻", 15.0, 40), ("30", "刻蚀", 10.0, 60), ("40", "去胶", 3.0, 200), ("50", "量测", 5.0, 120)],
        [("10", "薄膜沉积", 20.0, 30), ("20", "光刻", 15.0, 40), ("30", "刻蚀", 10.0, 60), ("40", "退火", 30.0, 20), ("50", "量测", 5.0, 120)],
        [("10", "氧化", 25.0, 24), ("20", "CVD沉积", 18.0, 33), ("30", "光刻", 15.0, 40), ("40", "刻蚀", 10.0, 60), ("50", "离子注入", 12.0, 50), ("60", "退火", 30.0, 20)],
    ]
    routings_created = []
    for i, prod in enumerate(prod_objs[:3]):
        steps = routing_steps_def[i % len(routing_steps_def)]
        r = Routing(
            product_id=prod.id,
            version=f"v1.{i+1}",
            status=RoutingStatus.EFFECTIVE.value,
            effective_date=now - timedelta(days=30),
            next_review_date=now + timedelta(days=335),
            change_reason="NEW" if i == 0 else "ENG_CHG",
            remark=f"{prod.name} 工艺路线",
            created_by_id=users.get("process1", list(users.values())[0]).id if users else None,
            created_by_name=users.get("process1", list(users.values())[0]).username if users else "system",
        )
        db.add(r)
        db.flush()
        for seq, name, cycle, uph in steps:
            s = RoutingStep(
                routing_id=r.id,
                seq=int(seq),
                step_name=name,
                standard_cycle_min=cycle,
                theoretical_uph=uph,
                acceptance_criteria="全检合格率>=98%",
                equipment_group="通用设备组",
                required_skill_level="L2",
            )
            db.add(s)
        routings_created.append(r)

    # 2. 生产订单（MO）
    mo_statuses = [
        (ProductionOrderStatus.IN_PROGRESS.value, 800, 600, 20),
        (ProductionOrderStatus.IN_PROGRESS.value, 1200, 900, 30),
        (ProductionOrderStatus.RELEASED.value, 1000, 0, 0),
        (ProductionOrderStatus.COMPLETED.value, 500, 480, 10),
        (ProductionOrderStatus.IN_PROGRESS.value, 2000, 1500, 50),
    ]
    mo_objs = []
    for i, (status, plan, completed, scrapped) in enumerate(mo_statuses):
        prod = prod_objs[i % len(prod_objs)]
        routing = routings_created[i % len(routings_created)] if routings_created else None
        mo = ProductionOrder(
            mo_no=f"MO-{now.strftime('%Y%m%d')}-{i+1:04d}",
            product_id=prod.id,
            routing_id=routing.id if routing else None,
            batch_no=f"B{now.strftime('%Y%m%d')}-MO{i+1}",
            priority="HIGH" if i < 2 else "NORMAL",
            status=status,
            source_type=MOSourceType.MANUAL.value,
            plan_qty=plan,
            input_qty=completed + scrapped + random.randint(50, 200) if status != ProductionOrderStatus.RELEASED.value else 0,
            completed_qty=completed,
            scrapped_qty=scrapped,
            planned_start=today_start - timedelta(days=random.randint(0, 3)),
            planned_end=today_start + timedelta(days=random.randint(1, 7)),
            actual_start=now - timedelta(hours=random.randint(2, 12)) if status in (ProductionOrderStatus.IN_PROGRESS.value, ProductionOrderStatus.COMPLETED.value) else None,
            actual_end=now - timedelta(hours=1) if status == ProductionOrderStatus.COMPLETED.value else None,
            created_by_id=users.get("prod_mgr1", list(users.values())[0]).id if users else None,
            created_by_name=users.get("prod_mgr1", list(users.values())[0]).username if users else "system",
        )
        db.add(mo)
        mo_objs.append(mo)
    db.flush()

    # 3. 派工单（每条在产MO 2~3个派工）
    dispatch_count = 0
    running_eqs = [e for e in eqs if e.current_status in ("RUN", "IDLE")]
    for mo in mo_objs:
        if mo.status not in (ProductionOrderStatus.IN_PROGRESS.value, ProductionOrderStatus.RELEASED.value):
            continue
        num_dispatches = min(3, len(running_eqs))
        for j in range(num_dispatches):
            eq = running_eqs[(mo.id + j) % len(running_eqs)]
            op = users.get("operator1") or users.get("operator2") or list(users.values())[0]
            is_running = mo.status == ProductionOrderStatus.IN_PROGRESS.value and j == 0
            dispatch_qty = mo.plan_qty // num_dispatches
            completed = mo.completed_qty // num_dispatches if is_running else 0
            d = Dispatch(
                mo_id=mo.id,
                step_seq=10 + j * 10,
                step_name=["清洗", "光刻", "刻蚀"][j % 3],
                equipment_id=eq.id,
                assigned_operator_id=op.id,
                assigned_team="甲班" if j % 2 == 0 else "乙班",
                dispatch_qty=dispatch_qty,
                completed_qty=completed,
                scrapped_qty=0,
                wip_qty=dispatch_qty - completed,
                status=DispatchStatus.RUNNING.value if is_running else (DispatchStatus.ASSIGNED.value if mo.status == ProductionOrderStatus.RELEASED.value else DispatchStatus.QUEUED.value),
                planned_start=now - timedelta(hours=2),
                planned_end=now + timedelta(hours=6),
                actual_start=now - timedelta(hours=2) if is_running else None,
            )
            db.add(d)
            dispatch_count += 1

            # 4. 报工记录（RUNNING的派工有1~2条报工）
            if is_running:
                db.flush()  # 确保 d.id 存在
                for k in range(random.randint(1, 2)):
                    lr = LaborReport(
                        dispatch_id=d.id,
                        reporter_id=op.id,
                        reporter_name=op.username,
                        report_time=now - timedelta(hours=random.randint(1, 5)),
                        session_start=now - timedelta(hours=random.randint(3, 6)),
                        session_end=now - timedelta(hours=random.randint(1, 3)),
                        input_qty=random.randint(50, 200),
                        good_qty=random.randint(45, 195),
                        defect_qty=random.randint(0, 10),
                        man_hours=float(random.randint(2, 4)),
                        remark="正常生产",
                    )
                    db.add(lr)
    db.commit()
    print(f"    + 工序路由: {len(routings_created)} 个, 生产订单: {len(mo_objs)} 条, 派工: {dispatch_count} 条")


# =====================================================================
#  汇总打印
# =====================================================================

def _print_summary(db):
    from app.models import (
        EquipmentStatusLog, EquipmentAttachment, SparePartMovement,
        InspectionItem, InspectionResult, FiveWhy, FormRecordValue,
        D8Report, Product, ProductionRecord,
        Routing, RoutingStep, ProductionOrder, Dispatch, LaborReport,
    )
    stats = [
        ("用户 User",                   db.query(User).count()),
        ("设备 Equipment",               db.query(Equipment).count()),
        ("设备状态日志",                 db.query(EquipmentStatusLog).count()),
        ("设备附件",                     db.query(EquipmentAttachment).count()),
        ("备件 SparePart",               db.query(SparePart).count()),
        ("设备-易损件关联",              db.query(EquipmentSparePart).count()),
        ("备件出入库记录",               db.query(SparePartMovement).count()),
        ("备件领用",                     db.query(SparePartUsage).count()),
        ("点检模板",                     db.query(InspectionTemplate).count()),
        ("点检检查项",                   db.query(InspectionItem).count()),
        ("点检记录",                     db.query(InspectionRecord).count()),
        ("点检逐项结果",                 db.query(InspectionResult).count()),
        ("工单 WorkOrder",               db.query(WorkOrder).count()),
        ("报修单 RepairReport",          db.query(RepairReport).count()),
        ("8D报告 D8Report",              db.query(D8Report).count()),
        ("FiveWhy 分析",                 db.query(FiveWhy).count()),
        ("工艺文件 ProcessDocument",     db.query(ProcessDocument).count()),
        ("表单模板 FormTemplate",        db.query(FormTemplate).count()),
        ("表单记录 FormRecord",          db.query(FormRecord).count()),
        ("表单字段值",                   db.query(FormRecordValue).count()),
        ("表单修正记录",                 db.query(FormRecordAmendment).count()),
        ("安全检查 SafetyInspection",    db.query(SafetyInspection).count()),
        ("设备生命周期",                 db.query(EquipmentLifecycle).count()),
        ("润滑点 LubricationPoint",      db.query(LubricationPoint).count()),
        ("润滑执行记录",                 db.query(LubricationRecord).count()),
        ("故障知识库",                   db.query(KnowledgeEntry).count()),
        ("设备成本 EquipmentCost",       db.query(EquipmentCost).count()),
        ("产品 Product",                 db.query(Product).count()),
        ("生产记录 ProductionRecord",    db.query(ProductionRecord).count()),
        ("工序路由 Routing",              db.query(Routing).count()),
        ("工序步骤 RoutingStep",          db.query(RoutingStep).count()),
        ("生产订单 ProductionOrder",      db.query(ProductionOrder).count()),
        ("派工单 Dispatch",              db.query(Dispatch).count()),
        ("报工记录 LaborReport",         db.query(LaborReport).count()),
    ]
    print("\n" + "=" * 55)
    print("📊 SEMS 全模块数据汇总")
    print("=" * 55)
    for name, cnt in stats:
        print(f"  {name:30s}: {cnt}")
    print("=" * 55)


# =====================================================================
#  主函数
# =====================================================================

def main():
    db = SessionLocal()
    try:
        print("🔧 重建数据库表...")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        print("✅ 表结构重建完成\n")

        # 基础数据
        users = _seed_users(db)
        eqs = _seed_equipment(db)
        _seed_equipment_status_logs(db, eqs, users)
        _seed_equipment_attachments(db, eqs, users)

        # 支撑资源
        parts = _seed_spare_parts(db)
        _seed_equipment_spare_parts(db, eqs, parts)
        _seed_spare_part_movements(db, parts, users)

        # 日常运维
        templates = _seed_inspection_templates(db, eqs)
        _seed_inspection_records(db, templates, eqs, users)
        work_orders = _seed_work_orders(db, eqs, users)
        _seed_repair_reports_and_five_whys(db, eqs, users, work_orders)
        _seed_spare_part_usages(db, parts, work_orders, users)
        d8_reports = _seed_d8_reports(db, eqs, work_orders, users)

        # 工艺文控
        form_tpls = _seed_form_templates(db, eqs, users)
        form_recs = _seed_form_records(db, form_tpls, eqs, users)
        _seed_form_record_amendments(db, form_recs, users)
        _seed_process_documents(db, eqs, users)

        # 合规安全
        _seed_safety_inspections(db, eqs, users)

        # 设备全生命周期
        _seed_equipment_lifecycle(db, eqs, users)

        # 润滑管理
        lub_points = _seed_lubrication_points(db, eqs, users)
        _seed_lubrication_records(db, lub_points, users)

        # 数据价值
        _seed_knowledge_entries(db, eqs, work_orders, users)
        _seed_equipment_costs(db, eqs, work_orders, users)

        # 产品与生产记录（生产管理角色看板数据）
        prod_objs = _seed_products_and_production(db, eqs, users)

        # 生产管理模块（路由/生产订单/派工/报工）
        _seed_production_management(db, prod_objs, eqs, users)

        db.commit()
        _print_summary(db)
        print("\n✅ SEMS 全模块测试数据生成完毕！")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
