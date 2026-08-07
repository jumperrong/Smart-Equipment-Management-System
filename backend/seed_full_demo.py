"""全模块模拟数据生成脚本。

运行方式: cd backend && .venv/bin/python seed_full_demo.py

覆盖模块:
- 用户（工程师/操作员/查看者）
- 产品 + 生产记录（OEE 支撑）
- 工单（PM/REPAIR/REPORT 各状态）
- 报修单 + 转单
- Five-Why 分析
- 备件领用（工单关联）
- 环境核查记录
- 人员资质 + 培训
- 8D 报告 + FMEA
- 资产盘点 + 调拨申请
- 设备附件
"""
import os
import sys
import random
import pathlib
from datetime import datetime, timedelta

# 确保 backend 目录在 path
os.chdir(pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, ".")

from app.core.database import SessionLocal, engine
from app.models import (
    Base, User, UserRole, Equipment, EquipmentStatus,
    WorkOrder, WorkOrderType, WorkOrderStatus, RepairReport,
    FiveWhy, SparePart, SparePartMovement, SparePartUsage,
    PMPlan, Product, ProductionRecord,
    EnvironmentLog, Qualification, Training, TrainingAttendee,
    D8Report, D8Status, FMEA, FMEAItem,
    AssetInventory, AssetInventoryLine, AssetApplication,
    EquipmentAttachment, SkillLevel, ProcessDocument,
)
from app.services.user_service import get_password_hash

random.seed(42)

def main():
    db = SessionLocal()
    try:
        # ---- 用户 ----
        users = _ensure_users(db)
        admin = next(u for u in users if u.role == UserRole.ADMIN)
        engineers = [u for u in users if u.role == UserRole.ENGINEER]
        process_engineers = [u for u in users if u.role == UserRole.PROCESS_ENGINEER]
        operators = [u for u in users if u.role == UserRole.OPERATOR]

        # ---- 设备 ----
        equipments = db.query(Equipment).filter(Equipment.is_active == True).all()
        if not equipments:
            print("⚠ 无设备数据，请先运行 init_db")
            return

        # ---- 产品 ----
        products = _ensure_products(db)

        # ---- 生产记录 ----
        _seed_production_records(db, equipments, products, operators)

        # ---- 工单 ----
        _seed_work_orders(db, equipments, users)

        # ---- 报修单 ----
        _seed_repair_reports(db, equipments, operators, engineers)

        # ---- 环境核查 ----
        _seed_environment_logs(db, equipments, operators)

        # ---- 人员资质 ----
        _seed_qualifications(db, users, equipments, admin)

        # ---- 培训 ----
        _seed_trainings(db, users, equipments, engineers)

        # ---- 8D 报告 ----
        _seed_d8_reports(db, equipments, users)

        # ---- FMEA ----
        _seed_fmeas(db, equipments, engineers)

        # ---- 资产盘点 ----
        _seed_asset_inventories(db, equipments, users)

        # ---- 资产调拨/报废 ----
        _seed_asset_applications(db, equipments, users)

        # ---- 设备附件 ----
        _seed_equipment_attachments(db, equipments, admin)

        # ---- 工艺文件 ----
        _seed_process_documents(db, equipments, process_engineers or engineers or [admin])

        db.commit()
        print("\n✅ 全模块模拟数据生成完毕！")
        _print_summary(db)

    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


# ============ 用户 ============

def _ensure_users(db) -> list[User]:
    """确保有 admin + 2工程师 + 1工艺员 + 3操作员 + 1查看者"""
    defs = [
        ("engineer1", "张工", UserRole.ENGINEER, "eng123"),
        ("engineer2", "李工", UserRole.ENGINEER, "eng123"),
        ("process1", "周工艺", UserRole.PROCESS_ENGINEER, "proc123"),
        ("operator1", "王操作", UserRole.OPERATOR, "op123"),
        ("operator2", "赵操作", UserRole.OPERATOR, "op123"),
        ("operator3", "钱操作", UserRole.OPERATOR, "op123"),
        ("viewer1", "孙查看", UserRole.VIEWER, "view123"),
    ]
    users = []
    for username, full_name, role, pwd in defs:
        u = db.query(User).filter(User.username == username).first()
        if u is None:
            u = User(
                username=username,
                full_name=full_name,
                hashed_password=get_password_hash(pwd),
                role=role,
                is_active=True,
            )
            db.add(u)
            db.flush()
            print(f"  + 用户: {username} ({full_name}, {role.value})")
        users.append(u)
    # admin
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if admin:
        users.append(admin)
    db.flush()
    return users


# ============ 产品 ============

def _ensure_products(db) -> list[Product]:
    """创建半导体产品"""
    defs = [
        ("P001", "12寸晶圆-A型", "12inch Wafer Type A", "片", 60),
        ("P002", "12寸晶圆-B型", "12inch Wafer Type B", "片", 90),
        ("P003", "8寸晶圆-C型", "8inch Wafer Type C", "片", 120),
    ]
    products = []
    for code, name, spec, unit, cycle in defs:
        p = db.query(Product).filter(Product.code == code).first()
        if p is None:
            p = Product(code=code, name=name, spec=spec, unit=unit, target_cycle=cycle, is_active=True)
            db.add(p)
            db.flush()
        products.append(p)
    db.flush()
    return products


# ============ 生产记录 ============

def _seed_production_records(db, equipments, products, operators):
    """为每台设备生成过去 7 天的生产记录"""
    existing = db.query(ProductionRecord).count()
    if existing > 50:
        print(f"  ~ 生产记录已存在({existing}条)，跳过")
        return
    now = datetime.now()
    count = 0
    for eq in equipments:
        if eq.current_status in (EquipmentStatus.OFFLINE,):
            continue
        for day_offset in range(7, 0, -1):
            base = now - timedelta(days=day_offset)
            # 每天 1-2 条记录
            for shift_idx in range(random.randint(1, 2)):
                product = random.choice(products)
                start = base.replace(hour=8+shift_idx*8, minute=0, second=0, microsecond=0)
                duration = random.randint(400, 480)
                end = start + timedelta(minutes=duration)
                plan_qty = random.randint(200, 400)
                input_qty = plan_qty + random.randint(-20, 20)
                defect_qty = random.randint(0, 15)
                good_qty = input_qty - defect_qty
                operator = random.choice(operators) if operators else None
                rec = ProductionRecord(
                    record_no=f"PR{base.strftime('%Y%m%d')}{eq.id:03d}{shift_idx}",
                    equipment_id=eq.id,
                    product_id=product.id,
                    batch_no=f"B{base.strftime('%Y%m%d')}-{eq.id}-{shift_idx+1}",
                    plan_qty=plan_qty,
                    input_qty=input_qty,
                    good_qty=good_qty,
                    defect_qty=defect_qty,
                    start_time=start,
                    end_time=end,
                    duration_minutes=duration,
                    ideal_cycle=product.target_cycle,
                    operator_id=operator.id if operator else None,
                    remark="" if random.random() > 0.2 else "生产正常",
                )
                db.add(rec)
                count += 1
    db.flush()
    print(f"  + 生产记录: {count} 条")


# ============ 工单 ============

def _seed_work_orders(db, equipments, users):
    """生成各类型/状态的工单"""
    existing = db.query(WorkOrder).count()
    if existing > 20:
        print(f"  ~ 工单已存在({existing}条)，跳过")
        return

    engineers = [u for u in users if u.role == UserRole.ENGINEER]
    operators = [u for u in users if u.role == UserRole.OPERATOR]
    now = datetime.now()
    count = 0

    # PM 工单（已完成）
    for eq in equipments[:5]:
        wo = _create_wo(
            db, WorkOrderType.PM, WorkOrderStatus.COMPLETED, eq,
            f"{eq.name} 季度PM保养",
            "按PM计划执行：清洁、润滑、校准、更换易损件",
            assignee=random.choice(engineers) if engineers else None,
            planned_start=now - timedelta(days=random.randint(5, 20)),
            actual_start=now - timedelta(days=random.randint(5, 20)),
            actual_end=now - timedelta(days=random.randint(4, 19)),
            fault_category=None,
        )
        count += 1

    # PM 工单（进行中）
    for eq in equipments[5:8]:
        _create_wo(
            db, WorkOrderType.PM, WorkOrderStatus.IN_PROGRESS, eq,
            f"{eq.name} 月度PM保养",
            "执行月度保养：检查真空度、校准温度、清洁腔体",
            assignee=random.choice(engineers) if engineers else None,
            planned_start=now - timedelta(hours=2),
            actual_start=now - timedelta(hours=2),
        )
        count += 1

    # 维修工单（已完成）
    repair_descs = [
        ("真空泵异常噪音", "MECHANICAL", "轴承磨损，已更换", "定期更换轴承，增加点检频率"),
        ("温度控制偏差", "ELECTRICAL", "温度传感器老化，校准后恢复", "建立传感器寿命台账，到期更换"),
        ("通讯超时", "SOFTWARE", "PLC固件bug，升级后解决", "加强固件版本管理"),
        ("气压不稳定", "MECHANICAL", "过滤器堵塞，清洗后恢复", "缩短过滤器更换周期"),
    ]
    for i, (phenom, cat, sol, prev) in enumerate(repair_descs):
        eq = equipments[i % len(equipments)]
        wo = _create_wo(
            db, WorkOrderType.REPAIR, WorkOrderStatus.COMPLETED, eq,
            f"{eq.name} 维修: {phenom}",
            f"故障现象: {phenom}",
            assignee=random.choice(engineers) if engineers else None,
            planned_start=now - timedelta(days=random.randint(1, 10)),
            actual_start=now - timedelta(days=random.randint(1, 10)),
            actual_end=now - timedelta(days=random.randint(0, 9)),
            fault_category=cat,
            root_cause=sol.split("，")[0],
            solution=sol,
            prevention=prev,
        )
        # 添加 Five-Why
        _add_five_whys(db, wo, phenom)
        count += 1

    # 维修工单（进行中）
    for eq in equipments[2:5]:
        _create_wo(
            db, WorkOrderType.REPAIR, WorkOrderStatus.IN_PROGRESS, eq,
            f"{eq.name} 紧急维修",
            "设备报警停机，初步判断为传感器故障",
            assignee=random.choice(engineers) if engineers else None,
            actual_start=now - timedelta(hours=1),
        )
        count += 1

    # 维修工单（已创建待分配）
    for eq in equipments[6:9]:
        _create_wo(
            db, WorkOrderType.REPAIR, WorkOrderStatus.CREATED, eq,
            f"{eq.name} 异常待处理",
            "操作员报告设备运行声音异常",
        )
        count += 1

    # 备件领用（关联已完成的维修工单）
    completed_wos = db.query(WorkOrder).filter(WorkOrder.status == WorkOrderStatus.COMPLETED).all()
    spare_parts = db.query(SparePart).all()
    if completed_wos and spare_parts:
        for wo in completed_wos[:4]:
            part = random.choice(spare_parts)
            qty = random.randint(1, 3)
            if part.current_stock >= qty:
                # 扣库存
                before = part.current_stock
                part.current_stock -= qty
                mv = SparePartMovement(
                    spare_part_id=part.id, movement_type="OUT", qty=qty,
                    before_stock=before, after_stock=part.current_stock,
                    ref_type="WORK_ORDER", ref_id=wo.id,
                    operator_id=wo.assignee_id, remark=f"工单领用: {wo.title}",
                )
                db.add(mv)
                db.flush()
                usage = SparePartUsage(
                    work_order_id=wo.id, spare_part_id=part.id, qty=qty,
                    movement_id=mv.id, remark="维修领用",
                )
                db.add(usage)
        count += 4

    db.flush()
    print(f"  + 工单: {count} 条（含 Five-Why + 备件领用）")


def _create_wo(db, wtype, status, eq, title, desc, assignee=None,
               planned_start=None, actual_start=None, actual_end=None,
               fault_category=None, root_cause=None, solution=None, prevention=None):
    now = datetime.now()
    seq = db.query(WorkOrder).count() + 1
    wo = WorkOrder(
        order_no=f"WO{now.strftime('%Y%m%d')}{seq:03d}",
        type=wtype, status=status,
        equipment_id=eq.id,
        title=title, description=desc,
        assignee_id=assignee.id if assignee else None,
        fault_category=fault_category,
        root_cause=root_cause, solution=solution, prevention=prevention,
        planned_start=planned_start, actual_start=actual_start,
        actual_end=actual_end,
        completed_at=actual_end if status == WorkOrderStatus.COMPLETED else None,
    )
    db.add(wo)
    db.flush()
    return wo


def _add_five_whys(db, wo, phenomenon):
    qs = [
        f"为什么出现{phenomenon}？", "为什么部件会磨损？",
        "为什么润滑不足？", "为什么保养周期过长？", "如何预防？"
    ]
    ans = [
        "部件磨损导致", "润滑不足导致", "保养周期设置过长",
        "未根据实际工况调整保养频率", "建立动态保养周期模型"
    ]
    for i, (q, a) in enumerate(zip(qs, ans), 1):
        db.add(FiveWhy(work_order_id=wo.id, seq=i, question=q, answer=a))
    db.flush()


# ============ 报修单 ============

def _seed_repair_reports(db, equipments, operators, engineers):
    existing = db.query(RepairReport).count()
    if existing > 5:
        print(f"  ~ 报修单已存在({existing}条)，跳过")
        return

    now = datetime.now()
    phenomena = [
        ("设备运行时发出异常噪音", "HIGH"),
        ("产品良率突然下降", "CRITICAL"),
        ("设备显示报警信息", "NORMAL"),
        ("气路压力不稳定", "HIGH"),
        ("温度显示异常", "NORMAL"),
    ]
    count = 0
    for i, (phen, urgency) in enumerate(phenomena):
        eq = equipments[i % len(equipments)]
        reporter = random.choice(operators) if operators else None
        rpt = RepairReport(
            equipment_id=eq.id,
            reporter_id=reporter.id if reporter else None,
            phenomenon=phen,
            urgency=urgency,
            reported_at=now - timedelta(days=random.randint(0, 5), hours=random.randint(0, 8)),
            status="OPEN" if i < 2 else "CONVERTED",
        )
        db.add(rpt)
        db.flush()
        count += 1

        # 把后 3 条转成工单
        if i >= 2:
            wo = _create_wo(
                db, WorkOrderType.REPAIR, WorkOrderStatus.ASSIGNED, eq,
                f"{eq.name} 报修转单: {phen[:15]}",
                f"由报修单转单。现象: {phen}",
                assignee=random.choice(engineers) if engineers else None,
            )
            rpt.status = "CONVERTED"
            rpt.work_order_id = wo.id

    db.flush()
    print(f"  + 报修单: {count} 条（含 {count-2} 条已转单）")


# ============ 环境核查 ============

def _seed_environment_logs(db, equipments, operators):
    existing = db.query(EnvironmentLog).count()
    if existing > 20:
        print(f"  ~ 环境核查已存在({existing}条)，跳过")
        return

    now = datetime.now()
    factories = set(eq.factory for eq in equipments)
    areas = set((eq.factory, eq.area) for eq in equipments)
    count = 0
    for day_offset in range(7, 0, -1):
        base = now - timedelta(days=day_offset)
        for factory, area in list(areas)[:4]:
            for shift in ("A", "B"):
                inspector = random.choice(operators) if operators else None
                is_ok = random.random() > 0.1
                log = EnvironmentLog(
                    log_date=base.date(),
                    factory=factory, area=area, shift=shift,
                    temperature=round(random.uniform(21.0, 25.0), 1),
                    humidity=round(random.uniform(40.0, 55.0), 1),
                    cleanliness="CLEAN" if is_ok else random.choice(["WARN", "DIRTY"]),
                    particles=random.randint(1, 100),
                    pressure=round(random.uniform(-50.0, -30.0), 1),
                    result="OK" if is_ok else "NG",
                    inspector_id=inspector.id if inspector else None,
                    remark="" if is_ok else "需复检",
                )
                db.add(log)
                count += 1
    db.flush()
    print(f"  + 环境核查: {count} 条")


# ============ 人员资质 ============

def _seed_qualifications(db, users, equipments, admin):
    existing = db.query(Qualification).count()
    if existing > 10:
        print(f"  ~ 资质已存在({existing}条)，跳过")
        return
    now = datetime.now()
    ops_and_engs = [u for u in users if u.role in (UserRole.OPERATOR, UserRole.ENGINEER)]
    count = 0
    for user in ops_and_engs:
        # 每人 1-3 个设备资质
        num = random.randint(1, min(3, len(equipments)))
        for eq in random.sample(equipments, num):
            level = random.choice(list(SkillLevel))
            cert_date = now - timedelta(days=random.randint(30, 365))
            exp_date = cert_date + timedelta(days=365)
            db.add(Qualification(
                user_id=user.id, equipment_id=eq.id,
                skill_level=level,
                certified_at=cert_date, expires_at=exp_date,
                certified_by=admin.id,
                score=random.randint(80, 100),
                is_active=True,
            ))
            count += 1
    db.flush()
    print(f"  + 资质: {count} 条")


# ============ 培训 ============

def _seed_trainings(db, users, equipments, engineers):
    existing = db.query(Training).count()
    if existing > 5:
        print(f"  ~ 培训已存在({existing}条)，跳过")
        return
    now = datetime.now()
    ops_and_engs = [u for u in users if u.role in (UserRole.OPERATOR, UserRole.ENGINEER)]
    topics = [
        ("设备安全操作培训", "安全规范、紧急停机、个人防护"),
        ("PM保养实操培训", "PM计划执行、清洁润滑校准"),
        ("故障诊断入门", "常见故障识别、初步排查步骤"),
        ("备件管理流程", "出入库流程、安全库存、易损件识别"),
        ("品质意识培训", "品质标准、不良品识别、追溯流程"),
    ]
    count = 0
    for i, (name, content) in enumerate(topics):
        eq = random.choice(equipments)
        trainer = random.choice(engineers) if engineers else None
        plan_date = now - timedelta(days=random.randint(1, 30))
        completed_date = plan_date + timedelta(hours=2) if i < 3 else None
        status = "COMPLETED" if completed_date else ("IN_PROGRESS" if i == 3 else "PLANNED")
        t = Training(
            name=name, equipment_id=eq.id,
            trainer_id=trainer.id if trainer else None,
            planned_date=plan_date, completed_date=completed_date,
            content=content, status=status,
        )
        db.add(t)
        db.flush()
        # 添加参训人员
        attendees = random.sample(ops_and_engs, min(3, len(ops_and_engs)))
        for att in attendees:
            passed = status == "COMPLETED" and random.random() > 0.15
            db.add(TrainingAttendee(
                training_id=t.id, user_id=att.id,
                attendance="PRESENT" if status != "PLANNED" else "ABSENT",
                score=random.randint(70, 100) if status == "COMPLETED" else None,
                passed=passed,
            ))
        count += 1
    db.flush()
    print(f"  + 培训: {count} 条（含参训记录）")


# ============ 8D 报告 ============

def _seed_d8_reports(db, equipments, users):
    existing = db.query(D8Report).count()
    if existing > 3:
        print(f"  ~ 8D报告已存在({existing}条)，跳过")
        return
    now = datetime.now()
    reports = [
        ("8D-2026-001", "IM设备良率异常下降", "D8-问题: 产线IM设备连续3天良率下降5%"),
        ("8D-2026-002", "ET设备通讯故障", "D8-问题: ET设备与MES通讯中断导致停机"),
        ("8D-2026-003", "PVD腔体真空泄漏", "D8-问题: PVD设备腔体真空度不达标"),
    ]
    for i, (no, title, problem) in enumerate(reports):
        eq = equipments[i % len(equipments)]
        owner = random.choice(users)
        status = D8Status.CLOSED if i == 0 else (D8Status.IN_PROGRESS if i == 1 else D8Status.OPEN)
        db.add(D8Report(
            report_no=no, equipment_id=eq.id, title=title,
            problem=problem,
            d1_team="设备工程师+品质工程师+操作员",
            d2_problem_desc=f"详细描述: {title}",
            d3_interim="临时措施: 增加检测频率",
            d4_root_cause="根本原因: 分析中" if i > 0 else "根本原因: 温度传感器漂移",
            d5_permanent="永久对策: 更换传感器并建立校准周期" if i == 0 else "对策制定中",
            d6_implement="已实施更换" if i == 0 else None,
            d7_prevent="预防: 建立传感器寿命台账" if i == 0 else None,
            d8_recognition="团队认可: 全员参与" if i == 0 else None,
            status=status,
            owner_id=owner.id,
            closed_at=now - timedelta(days=5) if status == D8Status.CLOSED else None,
        ))
    db.flush()
    print(f"  + 8D报告: {len(reports)} 条")


# ============ FMEA ============

def _seed_fmeas(db, equipments, engineers):
    existing = db.query(FMEA).count()
    if existing > 2:
        print(f"  ~ FMEA已存在({existing}条)，跳过")
        return
    now = datetime.now()
    for i, eq in enumerate(equipments[:3]):
        fmea = FMEA(
            equipment_id=eq.id,
            name=f"{eq.name} 工艺FMEA v1.0",
            version="1.0", is_active=True,
        )
        db.add(fmea)
        db.flush()
        # 添加 FMEA 项
        items = [
            ("装片", "晶片偏移", "良率下降", "吸盘磨损", 8, 3, 5, "定期更换吸盘"),
            ("对准", "对准偏差", "套刻精度超标", "对准系统漂移", 9, 2, 4, "增加校准频率"),
            ("曝光", "剂量异常", "线宽偏差", "光源衰减", 7, 4, 3, "建立光源寿命监控"),
            ("显影", "显影不均", "图案缺陷", "喷嘴堵塞", 6, 3, 6, "增加清洗频次"),
        ]
        for seq, (step, mode, effect, cause, s, o, d, action) in enumerate(items, 1):
            owner = random.choice(engineers) if engineers else None
            db.add(FMEAItem(
                fmea_id=fmea.id, seq=seq,
                process_step=step, failure_mode=mode, failure_effect=effect,
                cause=cause, severity=s, occurrence=o, detection=d, rpn=s*o*d,
                recommended_action=action,
                action_owner_id=owner.id if owner else None,
                action_due_date=now + timedelta(days=30),
                action_status="OPEN",
            ))
    db.flush()
    print(f"  + FMEA: 3 份（含 {3*4} 个分析项）")


# ============ 资产盘点 ============

def _seed_asset_inventories(db, equipments, users):
    existing = db.query(AssetInventory).count()
    if existing > 2:
        print(f"  ~ 资产盘点已存在({existing}条)，跳过")
        return
    now = datetime.now()
    admin = next((u for u in users if u.role == UserRole.ADMIN), None)
    # 已完成盘点
    inv1 = AssetInventory(
        inventory_no="AI202607001",
        name="2026年Q2全厂资产盘点",
        plan_date=now - timedelta(days=30),
        status="COMPLETED",
        created_by=admin.id if admin else None,
        completed_at=now - timedelta(days=28),
        remark="Q2例行盘点",
    )
    db.add(inv1)
    db.flush()
    for eq in equipments:
        is_match = random.random() > 0.1
        db.add(AssetInventoryLine(
            inventory_id=inv1.id, equipment_id=eq.id,
            system_status=eq.current_status.value,
            actual_found=True,
            location_match=is_match,
            result="MATCH" if is_match else "MISMATCH",
            checked_by=random.choice(users).id,
            checked_at=now - timedelta(days=28),
            remark="" if is_match else "位置不一致，需核实",
        ))
    # 进行中盘点
    inv2 = AssetInventory(
        inventory_no="AI202608001",
        name="2026年8月专项盘点",
        plan_date=now,
        status="IN_PROGRESS",
        created_by=admin.id if admin else None,
    )
    db.add(inv2)
    db.flush()
    for eq in equipments[:5]:
        db.add(AssetInventoryLine(
            inventory_id=inv2.id, equipment_id=eq.id,
            system_status=eq.current_status.value,
            actual_found=False,
            location_match=False,
            result="PENDING",
            checked_by=None, checked_at=None,
        ))
    db.flush()
    print(f"  + 资产盘点: 2 份（含 {len(equipments)+5} 条明细）")


# ============ 资产调拨/报废 ============

def _seed_asset_applications(db, equipments, users):
    existing = db.query(AssetApplication).count()
    if existing > 3:
        print(f"  ~ 资产申请已存在({existing}条)，跳过")
        return
    now = datetime.now()
    ops = [u for u in users if u.role == UserRole.OPERATOR]
    admin = next((u for u in users if u.role == UserRole.ADMIN), None)
    apps = [
        ("TRANSFER", "FAB1-A区", "FAB1-B区", "产线调整需要"),
        ("SCRAP", "FAB1-C区", "", "设备老化，维修成本过高"),
        ("TRANSFER", "FAB2-A区", "FAB1-A区", "产能调配"),
    ]
    for i, (atype, from_loc, to_loc, reason) in enumerate(apps):
        eq = equipments[i % len(equipments)]
        status = "COMPLETED" if i == 0 else ("APPROVED" if i == 1 else "PENDING")
        applicant = random.choice(ops) if ops else None
        db.add(AssetApplication(
            application_no=f"AA20260800{i+1}",
            type=atype, equipment_id=eq.id,
            from_location=from_loc, to_location=to_loc,
            reason=reason, status=status,
            applicant_id=applicant.id if applicant else None,
            approver_id=admin.id if admin and status != "PENDING" else None,
            applied_at=now - timedelta(days=random.randint(1, 10)),
            approved_at=now - timedelta(days=random.randint(0, 8)) if status != "PENDING" else None,
            completed_at=now - timedelta(days=random.randint(0, 5)) if status == "COMPLETED" else None,
        ))
    db.flush()
    print(f"  + 资产申请: {len(apps)} 条")


# ============ 设备附件 ============

def _seed_equipment_attachments(db, equipments, admin):
    existing = db.query(EquipmentAttachment).count()
    if existing > 5:
        print(f"  ~ 设备附件已存在({existing}条)，跳过")
        return
    now = datetime.now()
    categories = ["SOP", "说明书", "图纸", "其他"]
    count = 0
    for eq in equipments[:5]:
        cat = random.choice(categories)
        db.add(EquipmentAttachment(
            equipment_id=eq.id,
            filename=f"{eq.name}_{cat}.pdf",
            stored_path=f"data/uploads/{eq.name}_{cat}.pdf",
            file_size=random.randint(100000, 5000000),
            file_type="pdf",
            category=cat,
            description=f"{eq.name}的{cat}文档",
            uploaded_by=admin.id,
        ))
        count += 1
    db.flush()
    print(f"  + 设备附件: {count} 条")


# ============ 工艺文件（与机台绑定，区别于设备维修保养附件） ============

def _seed_process_documents(db, equipments, process_engineers):
    """为每台设备生成工艺文件（Recipe/Flowchart/Spec）。

    注意：工艺文件不同于设备维修保养附件(EquipmentAttachment)，
    它记录工艺配方/流程图/规格书，并带版本与状态(草稿/生效/作废)。
    """
    existing = db.query(ProcessDocument).count()
    if existing > 5:
        print(f"  ~ 工艺文件已存在({existing}条)，跳过")
        return
    now = datetime.now()
    docs_def = [
        ("Recipe 配方", "Recipe", "V1.2", "生效", "标准生产配方"),
        ("工艺流程图", "Flowchart", "V2.0", "生效", "工序流程定义"),
        ("工艺规格书", "Spec", "V1.0", "草稿", "工艺参数规格"),
    ]
    count = 0
    for eq in equipments[:6]:
        for doc_name, doc_type, version, status, desc in docs_def:
            eff_date = now - timedelta(days=random.randint(10, 200)) if status == "生效" else None
            db.add(ProcessDocument(
                equipment_id=eq.id,
                doc_name=f"{eq.name}_{doc_name}",
                doc_type=doc_type,
                version=version,
                status=status,
                effective_date=eff_date,
                stored_path=f"seed_{eq.id}_{doc_type}.pdf",  # 演示数据仅占位路径
                file_size=random.randint(50000, 2000000),
                file_type="application/pdf",
                description=desc,
                uploaded_by=random.choice(process_engineers).id if process_engineers else None,
            ))
            count += 1
    db.flush()
    print(f"  + 工艺文件: {count} 条")


# ============ 汇总 ============

def _print_summary(db):
    from app.models import (
        EquipmentStatusLog, SparePartMovement, InspectionRecord,
    )
    stats = {
        "用户": db.query(User).count(),
        "设备": db.query(Equipment).count(),
        "设备状态日志": db.query(EquipmentStatusLog).count(),
        "PM计划": db.query(PMPlan).count(),
        "工单": db.query(WorkOrder).count(),
        "报修单": db.query(RepairReport).count(),
        "Five-Why": db.query(FiveWhy).count(),
        "备件": db.query(SparePart).count(),
        "备件流水": db.query(SparePartMovement).count(),
        "备件领用": db.query(SparePartUsage).count(),
        "产品": db.query(Product).count(),
        "生产记录": db.query(ProductionRecord).count(),
        "点检记录": db.query(InspectionRecord).count(),
        "环境核查": db.query(EnvironmentLog).count(),
        "资质": db.query(Qualification).count(),
        "培训": db.query(Training).count(),
        "8D报告": db.query(D8Report).count(),
        "FMEA": db.query(FMEA).count(),
        "FMEA项": db.query(FMEAItem).count(),
        "资产盘点": db.query(AssetInventory).count(),
        "资产申请": db.query(AssetApplication).count(),
        "设备附件": db.query(EquipmentAttachment).count(),
        "工艺文件": db.query(ProcessDocument).count(),
    }
    print("\n" + "=" * 50)
    print("📊 数据汇总")
    print("=" * 50)
    for name, count in stats.items():
        print(f"  {name:12s}: {count}")
    print("=" * 50)


if __name__ == "__main__":
    main()
