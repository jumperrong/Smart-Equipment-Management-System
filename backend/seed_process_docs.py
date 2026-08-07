"""定向种子脚本：确保工艺员账号 + 工艺文件演示数据存在。

运行: cd backend && .venv/bin/python seed_process_docs.py
独立于 seed_full_demo.py，避免历史 D8 唯一约束等幂等性问题影响。

演示数据特性：
- 为部分文档创建多版本（演示版本管理）
- 状态覆盖 草稿/生效/作废 三态（演示状态管理）
"""
import os
import sys
import uuid
import random
import pathlib
from datetime import datetime, timedelta

os.chdir(pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.models import User, UserRole, Equipment, ProcessDocument
from app.services.user_service import get_password_hash

random.seed(7)


def main():
    db = SessionLocal()
    try:
        # 1) 工艺员账号
        proc = db.query(User).filter(User.username == "process1").first()
        if proc is None:
            proc = User(
                username="process1",
                full_name="周工艺",
                hashed_password=get_password_hash("proc123"),
                role=UserRole.PROCESS_ENGINEER,
                is_active=True,
            )
            db.add(proc)
            db.flush()
            print(f"  + 工艺员账号: process1 (周工艺)")
        else:
            print(f"  ~ 工艺员账号已存在: process1 (id={proc.id})")

        uploader = proc

        # 2) 工艺文件演示数据
        existing = db.query(ProcessDocument).count()
        if existing > 0:
            print(f"  ~ 工艺文件已存在({existing}条)，跳过")
        else:
            equipments = db.query(Equipment).filter(Equipment.is_active == True).all()
            if not equipments:
                print("⚠ 无设备数据，请先运行 init_db")
                return
            now = datetime.now()
            docs_def = [
                ("Recipe 配方", "Recipe", "V1.2", "生效", "标准生产配方"),
                ("工艺流程图", "Flowchart", "V2.0", "生效", "工序流程定义"),
                ("工艺规格书", "Spec", "V1.0", "草稿", "工艺参数规格"),
                ("作业指导书", "其他", "V1.3", "作废", "旧版作业指导书"),
            ]
            count = 0
            for idx, eq in enumerate(equipments[:6]):
                for doc_name, doc_type, version, status, desc in docs_def:
                    eff_date = now - timedelta(days=random.randint(10, 200)) if status == "生效" else None
                    gid = uuid.uuid4().hex
                    # 决定是否创建 V2
                    create_v2 = idx < 2 and doc_type == "Recipe"
                    # V1 状态：若要创建 V2，V1 作为历史版本应为"作废"；否则按原 status
                    v1_status = "作废" if create_v2 else status
                    v1_latest = not create_v2  # 有 V2 时 V1 非最新
                    db.add(ProcessDocument(
                        equipment_id=eq.id,
                        category="guide",
                        doc_name=f"{eq.name}_{doc_name}",
                        doc_type=doc_type,
                        version=version,
                        version_seq=1,
                        group_id=gid,
                        is_latest=v1_latest,
                        status=v1_status,
                        effective_date=eff_date,
                        stored_path=f"seed_{eq.id}_{doc_type}.pdf",
                        file_size=random.randint(50000, 2000000),
                        file_type="application/pdf",
                        description=desc,
                        uploaded_by=uploader.id,
                    ))
                    count += 1

                    if create_v2:
                        v2_eff = now - timedelta(days=random.randint(1, 9))
                        db.add(ProcessDocument(
                            equipment_id=eq.id,
                            category="guide",
                            doc_name=f"{eq.name}_{doc_name}",
                            doc_type=doc_type,
                            version="V2.0",
                            version_seq=2,
                            group_id=gid,
                            is_latest=True,
                            status="生效",
                            effective_date=v2_eff,
                            stored_path=f"seed_{eq.id}_{doc_type}_v2.pdf",
                            file_size=random.randint(50000, 2000000),
                            file_type="application/pdf",
                            description="版本升级：调整配方参数",
                            uploaded_by=uploader.id,
                        ))
                        count += 1
            print(f"  + 指导性文件: {count} 条（含 2 个多版本文档）")

            # 3) 作业记录文件演示数据
            record_defs = [
                ("批次记录", "BatchRecord", "批次生产作业记录"),
                ("参数记录", "ParamLog", "关键工艺参数记录"),
                ("检验记录", "InspectionRecord", "工序质量检验记录"),
                ("交接班记录", "ShiftHandover", "班次交接记录"),
            ]
            shifts = ["A", "B", "C"]
            record_count = 0
            for eq in equipments[:6]:
                # 每台设备生成近 5 天的作业记录（每天 1-2 条）
                for d in range(5):
                    prod_date = now - timedelta(days=d)
                    batch_seq = random.randint(1, 3)
                    batch_no = f"B{prod_date.strftime('%Y%m%d')}-{eq.id:02d}-{batch_seq}"
                    # 每天随机 1-2 种记录类型
                    day_types = random.sample(record_defs, k=random.randint(1, 2))
                    for doc_name, doc_type, desc in day_types:
                        shift = random.choice(shifts)
                        # 部分作业记录为草稿（当日刚上传未审核）
                        status = "草稿" if (d == 0 and random.random() < 0.4) else "生效"
                        db.add(ProcessDocument(
                            equipment_id=eq.id,
                            category="record",
                            doc_name=f"{eq.name}_{doc_name}_{batch_no}",
                            doc_type=doc_type,
                            version="V1",
                            version_seq=1,
                            group_id=uuid.uuid4().hex,
                            is_latest=True,
                            status=status,
                            effective_date=prod_date if status == "生效" else None,
                            batch_no=batch_no,
                            shift=shift,
                            production_date=prod_date,
                            stored_path=f"seed_record_{eq.id}_{doc_type}_{d}.pdf",
                            file_size=random.randint(20000, 800000),
                            file_type="application/pdf",
                            description=desc,
                            uploaded_by=uploader.id,
                        ))
                        record_count += 1
            print(f"  + 作业记录文件: {record_count} 条")

        db.commit()
        print("\n✅ 工艺员 + 工艺文件种子完成")
    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
