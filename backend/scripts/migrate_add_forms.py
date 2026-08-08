#!/usr/bin/env python3
"""迁移脚本：添加表单模板与结构化表单记录模块。

执行顺序：
1) 新建表 form_templates / form_records / form_record_values （ORM create_all 自动补）
2) 为 process_documents 加列 form_record_id INTEGER 并建索引

幂等可重复执行。
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    from app.core.config import settings
    from app.core.database import Base, engine
    from app import models  # noqa: F401  触发模型注册

    # 1) 自动创建新表
    Base.metadata.create_all(bind=engine)
    print("[1/2] create_all OK (form_templates/form_records/form_record_values)")

    # 2) 针对 SQLite：给 process_documents 追加 form_record_id 列 + 索引（如果不存在）
    db_url = settings.SQLALCHEMY_DATABASE_URI
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.getcwd(), db_path)
    else:
        print(f"[WARN] 非 SQLite 数据库，不自动执行 SQLite DDL。请自行在对应 DB 执行: "
              f"ALTER TABLE process_documents ADD COLUMN form_record_id INTEGER NULL; "
              f"CREATE INDEX IF NOT EXISTS ix_process_documents_form_record_id ON process_documents(form_record_id);")
        print("[2/2] SKIPPED")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(process_documents)").fetchall()]
    if "form_record_id" not in cols:
        cur.execute(
            "ALTER TABLE process_documents ADD COLUMN form_record_id INTEGER REFERENCES form_records(id) ON DELETE SET NULL"
        )
        print("  + ALTER TABLE process_documents ADD form_record_id")
    else:
        print("  · form_record_id 已存在，跳过")
    # 建索引（若不存在，靠名称判重）
    idx_rows = cur.execute("PRAGMA index_list(process_documents)").fetchall()
    idx_names = {r[1] for r in idx_rows}
    if "ix_process_documents_form_record_id" not in idx_names:
        cur.execute(
            "CREATE INDEX ix_process_documents_form_record_id ON process_documents(form_record_id)"
        )
        print("  + CREATE INDEX ix_process_documents_form_record_id")
    else:
        print("  · index ix_process_documents_form_record_id 已存在，跳过")
    conn.commit()
    conn.close()
    print("[2/2] process_documents 列+索引 OK")
    print("\n迁移完成。")


if __name__ == "__main__":
    main()
