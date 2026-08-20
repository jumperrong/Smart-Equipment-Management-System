"""锑化铟（InSb）晶圆制备工艺示范数据。

将工艺流程分为三大阶段、12 道工序，并作为产品/工段库/工序路由录入系统，
便于演示"产品 → 工段 → 路由 → 订单 → 派工 → 报工"的完整链路。

运行方式: cd backend && .venv/bin/python seed_insb_demo.py
"""
import os
import sys
import pathlib
from datetime import datetime

os.chdir(pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.models import (
    Product, ProcessSection, Routing, RoutingStep, RoutingStatus,
    User, UserRole,
)


# -------- 产品 --------
# 主产品：锑化铟晶圆；中间品：多晶锭、单晶锭，作为工艺路由上不同阶段的"虚拟产品"
# 便于单独按阶段下订单与在制追踪。
PRODUCTS = [
    {
        "code": "INSB-POLY-INGOT",
        "name": "锑化铟多晶锭（高纯）",
        "spec": "InSb 多晶 / 直径 30mm / 长度 200mm / 6N纯度",
        "unit": "锭",
        "target_cycle": None,
        "remark": "第一阶段产物：高纯 In 与 Sb 按 1:1 摩尔比合成 + 区熔提纯",
    },
    {
        "code": "INSB-SINGLE-INGOT",
        "name": "锑化铟单晶锭",
        "spec": "InSb 单晶 / <111>晶向 / 直径 50.8mm（2英寸） / N型",
        "unit": "锭",
        "target_cycle": None,
        "remark": "第二阶段产物：直拉法（CZ）生长，自动等径控制",
    },
    {
        "code": "INSB-WAFER-2IN",
        "name": "锑化铟晶圆 2英寸",
        "spec": "InSb 晶圆 / 2英寸 / <111> / 厚度 500μm / 双面抛光",
        "unit": "片",
        "target_cycle": 1800.0,  # 综合节拍，仅作参考
        "remark": "第三阶段最终产品：定向切片 → 倒角 → 研磨 → CMP → 清洗检测",
    },
]


# -------- 工段库 --------
# 每个 (阶段, 工序) 对应一个工段，绑定设备组与采集字段（描述写入 acceptance_criteria）
SECTIONS = [
    # 阶段 1：多晶原料合成
    {
        "code": "INSB-S01-POLY-SYNTH",
        "name": "多晶合成",
        "equipment_group": "多晶合成炉",
        "standard_cycle_min": 480.0,
        "theoretical_uph": 0.125,
        "required_skill_level": "工程师",
        "acceptance_criteria": "高纯 In + Sb 按 1:1 摩尔比；氢气保护气氛；温度 652℃ 完全熔合；锭条表面无氧化色斑。",
        "description": "在高温密闭容器中熔合铟与锑，合成 InSb 多晶锭条。",
    },
    {
        "code": "INSB-S01-ZONE-REFINE",
        "name": "区域熔炼提纯",
        "equipment_group": "区域熔炼炉",
        "standard_cycle_min": 720.0,
        "theoretical_uph": 0.083,
        "required_skill_level": "工程师",
        "acceptance_criteria": "区熔次数 ≥ 6 次；移动速度 1-2 mm/min；两端各切除 10% 后主体纯度 ≥ 6N。",
        "description": "通过移动加热区使杂质在锭条两端富集，主体获得高纯度多晶。",
    },
    # 阶段 2：单晶生长（CZ 法）
    {
        "code": "INSB-S02-CHARGE-MELT",
        "name": "装料与熔化",
        "equipment_group": "直拉单晶炉",
        "standard_cycle_min": 240.0,
        "theoretical_uph": 0.25,
        "required_skill_level": "工程师",
        "acceptance_criteria": "石英坩埚清洁度合格；真空 ≤ 5×10⁻⁴ Pa 后充氩气；熔体温度 652℃±1℃；液面无波动。",
        "description": "提纯后多晶原料装入石英坩埚，在直拉单晶炉内加热熔化。",
    },
    {
        "code": "INSB-S02-NECKING",
        "name": "引晶与缩颈",
        "equipment_group": "直拉单晶炉",
        "standard_cycle_min": 90.0,
        "theoretical_uph": 0.667,
        "required_skill_level": "工程师",
        "acceptance_criteria": "籽晶晶向 <111>；缩颈直径 2-3mm；颈长 ≥ 20mm；位错密度 < 100 /cm²。",
        "description": "籽晶插入熔体表面缓慢提拉并快速拉细以排除位错。",
    },
    {
        "code": "INSB-S02-SHOULDER-ISO",
        "name": "放肩与等径生长",
        "equipment_group": "直拉单晶炉",
        "standard_cycle_min": 720.0,
        "theoretical_uph": 0.083,
        "required_skill_level": "工程师",
        "acceptance_criteria": "目标直径 50.8mm；等径段直径偏差 ±0.2mm；自动等径控制启用；拉速 2-4 mm/h。",
        "description": "降低拉速使晶体长大至目标直径，随后维持直径恒定生长。",
    },
    {
        "code": "INSB-S02-TAIL-OFF",
        "name": "收尾与取出",
        "equipment_group": "直拉单晶炉",
        "standard_cycle_min": 180.0,
        "theoretical_uph": 0.333,
        "required_skill_level": "工程师",
        "acceptance_criteria": "收尾锥长 ≥ 30mm；脱离熔体后炉内冷却 ≤ 50℃/h；晶锭无裂纹。",
        "description": "缩小晶体直径使其与熔体脱离，炉内缓慢退火冷却减少热应力。",
    },
    # 阶段 3：晶圆加工
    {
        "code": "INSB-S03-XRAY-ORIENT",
        "name": "X射线定向",
        "equipment_group": "X射线晶体定向仪",
        "standard_cycle_min": 15.0,
        "theoretical_uph": 4.0,
        "required_skill_level": "工艺员",
        "acceptance_criteria": "晶向偏差 < 0.5°；标识基准面后再切割。",
        "description": "用 X 射线晶体定向仪确定晶锭晶向并标识基准面。",
    },
    {
        "code": "INSB-S03-WIRE-SAW",
        "name": "定向切割",
        "equipment_group": "单线切割机",
        "standard_cycle_min": 60.0,
        "theoretical_uph": 1.0,
        "required_skill_level": "操作员",
        "acceptance_criteria": "切片厚度 600±20μm；TTV < 10μm；切割损伤层 < 15μm；线痕均匀。",
        "description": "用高精度低损伤单线切割机将晶锭切片。",
    },
    {
        "code": "INSB-S03-EDGE-BEVEL",
        "name": "边缘倒角",
        "equipment_group": "倒角机",
        "standard_cycle_min": 5.0,
        "theoretical_uph": 12.0,
        "required_skill_level": "操作员",
        "acceptance_criteria": "倒角半径 R0.8±0.1mm；边缘无崩裂；表面无新损伤。",
        "description": "对切割后晶片边缘进行低损伤倒角，防止边缘崩裂。",
    },
    {
        "code": "INSB-S03-LAPPING",
        "name": "研磨平坦化",
        "equipment_group": "精密研磨机",
        "standard_cycle_min": 45.0,
        "theoretical_uph": 1.333,
        "required_skill_level": "操作员",
        "acceptance_criteria": "厚度 500±5μm；TTV < 3μm；研磨损伤层 < 8μm。",
        "description": "用精密研磨机配合研磨液去除切割损伤层并初步平坦化。",
    },
    {
        "code": "INSB-S03-CMP",
        "name": "化学机械抛光（CMP）",
        "equipment_group": "化学机械抛光机",
        "standard_cycle_min": 60.0,
        "theoretical_uph": 1.0,
        "required_skill_level": "工程师",
        "acceptance_criteria": "Ra < 0.5nm（AFM 测量）；无桔皮/划痕；厚度 500±2μm。",
        "description": "晶片粘贴在陶瓷载盘上，用优化配比的抛光液进行 CMP，获取原子级光滑表面。",
    },
    {
        "code": "INSB-S03-CLEAN-INSPECT",
        "name": "清洗与检测",
        "equipment_group": "清洗+检测设备组",
        "standard_cycle_min": 30.0,
        "theoretical_uph": 2.0,
        "required_skill_level": "工艺员",
        "acceptance_criteria": "颗粒数 ≥ 0.3μm ≤ 50/片；晶向偏差 < 0.3°；Ra < 0.5nm；TTV < 3μm；合格率 ≥ 95%。",
        "description": "抛光后严格清洗，并用 AFM、X 射线定向仪等设备检测表面粗糙度、晶向偏差、几何参数。",
    },
]


# -------- 工序路由 --------
# 每个产品一条路由，串起所属阶段工段；用 seq 10/20/30... 编号。
ROUTES = [
    {
        "product_code": "INSB-POLY-INGOT",
        "version": "v1.0",
        "change_reason": "初始版本：合成 + 区熔提纯",
        "remark": "阶段1 多晶原料合成",
        "steps": [
            ("INSB-S01-POLY-SYNTH", 10),
            ("INSB-S01-ZONE-REFINE", 20),
        ],
    },
    {
        "product_code": "INSB-SINGLE-INGOT",
        "version": "v1.0",
        "change_reason": "初始版本：CZ 法 4 工序",
        "remark": "阶段2 单晶生长（直拉法）",
        "steps": [
            ("INSB-S02-CHARGE-MELT", 10),
            ("INSB-S02-NECKING", 20),
            ("INSB-S02-SHOULDER-ISO", 30),
            ("INSB-S02-TAIL-OFF", 40),
        ],
    },
    {
        "product_code": "INSB-WAFER-2IN",
        "version": "v1.0",
        "change_reason": "初始版本：定向→切割→倒角→研磨→CMP→清洗检测",
        "remark": "阶段3 晶圆加工",
        "steps": [
            ("INSB-S03-XRAY-ORIENT", 10),
            ("INSB-S03-WIRE-SAW", 20),
            ("INSB-S03-EDGE-BEVEL", 30),
            ("INSB-S03-LAPPING", 40),
            ("INSB-S03-CMP", 50),
            ("INSB-S03-CLEAN-INSPECT", 60),
        ],
    },
]


def main():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        admin_id = admin.id if admin else None
        admin_name = admin.username if admin else "system"

        # ---- 产品（按 code upsert）----
        print("===== 产品 =====")
        for p in PRODUCTS:
            obj = db.query(Product).filter(Product.code == p["code"]).first()
            if obj:
                for k, v in p.items():
                    setattr(obj, k, v)
                obj.updated_at = datetime.utcnow()
                print(f"  ~ 更新产品 {obj.code} {obj.name}")
            else:
                obj = Product(**p, is_active=True)
                db.add(obj)
                db.flush()
                print(f"  + 新建产品 {obj.code} {obj.name}")

        # ---- 工段（按 code upsert）----
        print("\n===== 工段库 =====")
        section_by_code = {}
        for s in SECTIONS:
            obj = db.query(ProcessSection).filter(ProcessSection.code == s["code"]).first()
            payload = {k: v for k, v in s.items()}
            if obj:
                for k, v in payload.items():
                    setattr(obj, k, v)
                obj.is_active = True
                obj.updated_at = datetime.utcnow()
                print(f"  ~ 更新工段 {obj.code} {obj.name}")
            else:
                obj = ProcessSection(
                    **payload,
                    is_active=True,
                    created_by_id=admin_id,
                )
                db.add(obj)
                db.flush()
                print(f"  + 新建工段 {obj.code} {obj.name}")
            section_by_code[obj.code] = obj

        # ---- 路由（按 product_id + version upsert；已 EFFECTIVE 跳过避免冲突）----
        print("\n===== 工序路由 =====")
        for r in ROUTES:
            prod = db.query(Product).filter(Product.code == r["product_code"]).first()
            if not prod:
                print(f"  ! 产品 {r['product_code']} 不存在，跳过")
                continue
            existing = db.query(Routing).filter(
                Routing.product_id == prod.id,
                Routing.version == r["version"],
            ).first()
            if existing and existing.status == RoutingStatus.EFFECTIVE.value:
                print(f"  ~ 跳过 {prod.code} {r['version']}（已生效）")
                continue
            if existing:
                # 草稿/作废 → 删除旧步骤后重建为草稿
                db.query(RoutingStep).filter(RoutingStep.routing_id == existing.id).delete()
                routing = existing
                routing.status = RoutingStatus.DRAFT.value
                routing.change_reason = r["change_reason"]
                routing.remark = r["remark"]
                routing.effective_date = None
                routing.next_review_date = None
                print(f"  ~ 重建路由 {prod.code} {r['version']}（原状态草稿/作废）")
            else:
                routing = Routing(
                    product_id=prod.id,
                    version=r["version"],
                    status=RoutingStatus.DRAFT.value,
                    change_reason=r["change_reason"],
                    remark=r["remark"],
                    created_by_id=admin_id,
                    created_by_name=admin_name,
                )
                db.add(routing)
                db.flush()
                print(f"  + 新建路由 {prod.code} {r['version']}")

            for sec_code, seq in r["steps"]:
                sec = section_by_code.get(sec_code)
                step = RoutingStep(
                    routing_id=routing.id,
                    seq=seq,
                    step_name=sec.name,
                    process_section_id=sec.id,
                    standard_cycle_min=sec.standard_cycle_min,
                    theoretical_uph=sec.theoretical_uph,
                    equipment_group=sec.equipment_group,
                    required_skill_level=sec.required_skill_level,
                    acceptance_criteria=sec.acceptance_criteria,
                )
                db.add(step)
                db.flush()

            # 直接生效
            routing.status = RoutingStatus.EFFECTIVE.value
            routing.effective_date = datetime.utcnow()
            # 同产品其他生效版本作废
            db.query(Routing).filter(
                Routing.product_id == prod.id,
                Routing.status == RoutingStatus.EFFECTIVE.value,
                Routing.id != routing.id,
            ).update({"status": RoutingStatus.OBSOLETE.value})
            db.flush()
            print(f"  ✓ 路由已生效：{prod.code} {r['version']}（{(r['steps']).__len__()} 工序）")

        db.commit()
        print("\n✅ 锑化铟（InSb）晶圆工艺示范数据已写入")
        # 汇总
        n_p = db.query(Product).filter(Product.code.like("INSB-%")).count()
        n_s = db.query(ProcessSection).filter(ProcessSection.code.like("INSB-%")).count()
        n_r = db.query(Routing).filter(Routing.remark.like("%阶段%") | Routing.remark.like("%InSb%")).count()
        print(f"  产品 {n_p} 条 / 工段 {n_s} 条 / 路由 {len(ROUTES)} 条")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
