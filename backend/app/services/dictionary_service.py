from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.models import DictionaryItem, DictionaryCategory
from app.schemas import DictionaryItemCreate, DictionaryItemUpdate


# 内置字典种子数据（首次启动自动初始化）
SYSTEM_SEED = {
    DictionaryCategory.FACTORY: [
        ("FAB1", "FAB1 主厂区"),
        ("FAB2", "FAB2 二厂区"),
    ],
    DictionaryCategory.AREA: [
        ("WET", "湿法区"),
        ("DIFF", "扩散区"),
        ("CVD", "CVD 区"),
        ("ETCH", "刻蚀区"),
        ("LITHO", "光刻区"),
        ("PVD", "PVD 区"),
        ("CMP", "CMP 区"),
        ("IMPLANT", "注入区"),
        ("RTP", "退火区"),
        ("METRO", "量测区"),
    ],
    DictionaryCategory.EQUIPMENT_STATUS: [
        ("RUN", "运行"),
        ("IDLE", "待机"),
        ("DOWN", "故障"),
        ("PM", "维护"),
        ("ENGINEERING", "工程"),
        ("PROCESS_VALIDATION", "工艺验证"),
        ("OTHER", "其他"),
        ("OFFLINE", "离线"),
    ],
    DictionaryCategory.WORK_ORDER_TYPE: [
        ("REPAIR", "维修"),
        ("REPORT", "报修"),
        ("PM", "预防性维护"),
        ("INSPECTION", "巡检"),
        ("OTHER", "其他"),
    ],
    DictionaryCategory.SPARE_PART_CATEGORY: [
        ("SEAL", "密封件"),
        ("FILTER", "滤芯/滤网"),
        ("SENSOR", "传感器"),
        ("VALVE", "阀门"),
        ("PUMP", "泵"),
        ("BOARD", "电路板"),
        ("OTHER", "其他"),
    ],
    DictionaryCategory.REASON_CODE: [
        ("生产", "生产切换"),
        ("维护", "计划维护"),
        ("故障", "设备故障"),
        ("验证", "工艺验证"),
        ("切换", "产品切换"),
        ("待机", "无生产任务"),
    ],
}


def init_seed_dictionary(db: Session):
    """首次启动时初始化内置字典（已存在则跳过）"""
    for category, items in SYSTEM_SEED.items():
        existing = db.query(DictionaryItem).filter(DictionaryItem.category == category).count()
        if existing > 0:
            continue
        for idx, (code, label) in enumerate(items):
            item = DictionaryItem(
                category=category,
                code=code,
                label=label,
                value=code,
                sort_order=idx,
                is_active=True,
                is_system=True,
            )
            db.add(item)
    db.commit()


def list_items(
    db: Session,
    category: Optional[DictionaryCategory] = None,
    active_only: bool = False,
) -> List[DictionaryItem]:
    q = db.query(DictionaryItem)
    if category:
        q = q.filter(DictionaryItem.category == category)
    if active_only:
        q = q.filter(DictionaryItem.is_active.is_(True))
    return q.order_by(asc(DictionaryItem.sort_order), asc(DictionaryItem.id)).all()


def get_item(db: Session, item_id: int) -> Optional[DictionaryItem]:
    return db.query(DictionaryItem).filter(DictionaryItem.id == item_id).first()


def create_item(db: Session, obj_in: DictionaryItemCreate) -> DictionaryItem:
    # 同 category 下 code 唯一
    dup = db.query(DictionaryItem).filter(
        DictionaryItem.category == obj_in.category,
        DictionaryItem.code == obj_in.code,
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail=f"分类[{obj_in.category.value}]下已存在编码[{obj_in.code}]")
    data = obj_in.model_dump()
    if not data.get("value"):
        data["value"] = obj_in.code
    item = DictionaryItem(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: DictionaryItem, obj_in: DictionaryItemUpdate) -> DictionaryItem:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int):
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    if item.is_system:
        raise HTTPException(status_code=400, detail="系统内置字典项不可删除，可停用")
    db.delete(item)
    db.commit()


def categories_info() -> List[dict]:
    """返回字典分类的元信息"""
    return [
        {"value": c.value, "label": _category_label(c)}
        for c in DictionaryCategory
    ]


def _category_label(c: DictionaryCategory) -> str:
    return {
        DictionaryCategory.FACTORY: "厂区",
        DictionaryCategory.AREA: "区域",
        DictionaryCategory.EQUIPMENT_STATUS: "设备状态",
        DictionaryCategory.WORK_ORDER_TYPE: "工单类型",
        DictionaryCategory.SPARE_PART_CATEGORY: "备件分类",
        DictionaryCategory.REASON_CODE: "状态变更原因",
        DictionaryCategory.CUSTOM: "自定义",
    }.get(c, c.value)
