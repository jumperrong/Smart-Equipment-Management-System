from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Product, ProductionRecord, Equipment
from app.schemas import (
    ProductCreate, ProductUpdate,
    ProductionRecordCreate, ProductionRecordUpdate,
)


# ---------- Product ----------

def list_products(db: Session, active_only: bool = False):
    q = db.query(Product)
    if active_only:
        q = q.filter(Product.is_active.is_(True))
    return q.order_by(Product.id.desc()).all()


def get_product(db: Session, pid: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == pid).first()


def create_product(db: Session, obj_in: ProductCreate) -> Product:
    if db.query(Product).filter(Product.code == obj_in.code).first():
        raise HTTPException(status_code=400, detail="产品编号已存在")
    obj = Product(**obj_in.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_product(db: Session, obj: Product, obj_in: ProductUpdate) -> Product:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


def delete_product(db: Session, pid: int):
    obj = get_product(db, pid)
    if not obj:
        raise HTTPException(status_code=404, detail="产品不存在")
    db.delete(obj)
    db.commit()


def batch_import_products(db: Session, rows: list[dict]) -> dict:
    """批量导入产品。

    入参 rows 为字典列表，每个字典支持字段：
      code*, name*, spec, unit, target_cycle, remark, is_active
    - 必填字段缺失直接跳过并计入 failed
    - code 重复（DB 已存在或本次批次内重复）跳过
    - is_active 接受 'true'/'false'/'1'/'0'/True/False
    - target_cycle 接受数字字符串

    返回：{ok: int, failed: int, errors: [{row, reason}]}
    """
    seen_codes = set()
    # 预取已有 code，避免逐行查询
    existing = {c for (c,) in db.query(Product.code).all()}

    ok = 0
    failed = 0
    errors = []

    for idx, r in enumerate(rows, start=1):
        code = (r.get("code") or r.get("产品编号") or "").strip() if isinstance(r.get("code") or r.get("产品编号"), str) else (r.get("code") or r.get("产品编号"))
        name = (r.get("name") or r.get("产品名称") or "").strip() if isinstance(r.get("name") or r.get("产品名称"), str) else (r.get("name") or r.get("产品名称"))
        if not code or not name:
            failed += 1
            errors.append({"row": idx, "reason": "code/name 必填"})
            continue
        if code in existing or code in seen_codes:
            failed += 1
            errors.append({"row": idx, "reason": f"产品编号 {code} 已存在"})
            continue

        def _to_float(v):
            if v in (None, "", "-"):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def _to_bool(v):
            if isinstance(v, bool):
                return v
            if v in (None, ""):
                return True
            s = str(v).strip().lower()
            return s not in ("0", "false", "否", "停用")

        obj = Product(
            code=code,
            name=name,
            spec=(r.get("spec") or r.get("规格型号") or None) or None,
            unit=(r.get("unit") or r.get("单位") or "片") or "片",
            target_cycle=_to_float(r.get("target_cycle") or r.get("理论节拍")),
            remark=(r.get("remark") or r.get("备注") or None) or None,
            is_active=_to_bool(r.get("is_active") if "is_active" in r else r.get("启用", True)),
        )
        db.add(obj)
        seen_codes.add(code)
        ok += 1

    if ok:
        db.commit()
    return {"ok": ok, "failed": failed, "errors": errors}


# ---------- ProductionRecord ----------

def _gen_record_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    cnt = db.query(ProductionRecord).filter(ProductionRecord.record_no.like(f"PR{today}%")).count()
    return f"PR{today}{cnt + 1:03d}"


def list_production_records(
    db: Session,
    equipment_id: Optional[int] = None,
    product_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
):
    q = db.query(ProductionRecord)
    if equipment_id:
        q = q.filter(ProductionRecord.equipment_id == equipment_id)
    if product_id:
        q = q.filter(ProductionRecord.product_id == product_id)
    if start:
        q = q.filter(ProductionRecord.start_time >= start)
    if end:
        q = q.filter(ProductionRecord.start_time <= end)
    return q.order_by(ProductionRecord.id.desc()).offset(skip).limit(limit).all()


def get_production_record(db: Session, rid: int) -> Optional[ProductionRecord]:
    return db.query(ProductionRecord).filter(ProductionRecord.id == rid).first()


def create_production_record(db: Session, obj_in: ProductionRecordCreate) -> ProductionRecord:
    if not db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first():
        raise HTTPException(status_code=404, detail="设备不存在")
    data = obj_in.model_dump()
    # 自动计算时长
    if data.get("start_time") and data.get("end_time") and not data.get("duration_minutes"):
        delta = (data["end_time"] - data["start_time"]).total_seconds() / 60.0
        data["duration_minutes"] = round(delta, 2)
    # 自动填充理论节拍快照
    if not data.get("ideal_cycle"):
        eq = db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
        if eq and eq.theoretical_cycle:
            data["ideal_cycle"] = eq.theoretical_cycle
        if obj_in.product_id:
            prod = db.query(Product).filter(Product.id == obj_in.product_id).first()
            if prod and prod.target_cycle:
                data["ideal_cycle"] = prod.target_cycle
    obj = ProductionRecord(record_no=_gen_record_no(db), **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_production_record(db: Session, obj: ProductionRecord, obj_in: ProductionRecordUpdate) -> ProductionRecord:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    # 重新计算时长
    if obj.start_time and obj.end_time:
        obj.duration_minutes = round((obj.end_time - obj.start_time).total_seconds() / 60.0, 2)
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


def delete_production_record(db: Session, rid: int):
    obj = get_production_record(db, rid)
    if not obj:
        raise HTTPException(status_code=404, detail="生产记录不存在")
    db.delete(obj)
    db.commit()
