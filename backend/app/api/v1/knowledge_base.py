from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import KnowledgeEntry, WorkOrder, Equipment
from app.schemas import (
    KnowledgeEntryCreate, KnowledgeEntryOut, KnowledgeEntryUpdate,
    KnowledgeFromWorkOrder,
)
from app.services.user_service import get_current_user

router = APIRouter(prefix="/knowledge", tags=["故障知识库"])


def _user_display_name(user) -> str:
    return user.full_name or user.username


@router.get("", response_model=list[KnowledgeEntryOut])
def list_entries(
    keyword: Optional[str] = None,
    fault_category: Optional[str] = None,
    equipment_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """知识库列表，支持关键字搜索 title/symptom/root_cause/solution，
    以及按 fault_category / equipment_id / status 过滤。"""
    q = db.query(KnowledgeEntry)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                KnowledgeEntry.title.ilike(like),
                KnowledgeEntry.symptom.ilike(like),
                KnowledgeEntry.root_cause.ilike(like),
                KnowledgeEntry.solution.ilike(like),
            )
        )
    if fault_category:
        q = q.filter(KnowledgeEntry.fault_category == fault_category)
    if equipment_id is not None:
        q = q.filter(KnowledgeEntry.equipment_id == equipment_id)
    if status:
        q = q.filter(KnowledgeEntry.status == status)
    q = q.order_by(KnowledgeEntry.updated_at.desc())
    return q.offset(skip).limit(limit).all()


@router.post("", response_model=KnowledgeEntryOut)
def create_entry(
    obj_in: KnowledgeEntryCreate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    obj = KnowledgeEntry(
        **obj_in.model_dump(),
        created_by_id=current_user.id,
        created_by_name=_user_display_name(current_user),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/from-work-order/{work_order_id}", response_model=KnowledgeEntryOut)
def from_work_order(
    work_order_id: int,
    payload: Optional[KnowledgeFromWorkOrder] = None,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    """从工单归档为知识库条目：自动读取工单的 root_cause/solution/prevention 填充。"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")

    payload = payload or KnowledgeFromWorkOrder()

    # 故障分类：优先使用 payload，其次取工单的 fault_category(枚举转小写字符串)
    fc = payload.fault_category
    if not fc and wo.fault_category is not None:
        fc = wo.fault_category.value.lower() if hasattr(wo.fault_category, "value") else str(wo.fault_category).lower()

    title = payload.title or wo.title

    obj = KnowledgeEntry(
        title=title,
        symptom=wo.description,
        fault_category=fc,
        equipment_id=wo.equipment_id,
        equipment_model=payload.equipment_model,
        root_cause=wo.root_cause,
        solution=wo.solution,
        prevention=wo.prevention,
        source_work_order_id=wo.id,
        tags=payload.tags,
        status="active",
        created_by_id=current_user.id,
        created_by_name=_user_display_name(current_user),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/search", response_model=list[KnowledgeEntryOut])
def search_entries(
    q: str = Query(..., description="全文检索关键字: title/symptom/root_cause/solution/tags"),
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """全文检索：在 title/symptom/root_cause/solution/tags 上模糊匹配。"""
    like = f"%{q}%"
    rows = (
        db.query(KnowledgeEntry)
        .filter(
            or_(
                KnowledgeEntry.title.ilike(like),
                KnowledgeEntry.symptom.ilike(like),
                KnowledgeEntry.root_cause.ilike(like),
                KnowledgeEntry.solution.ilike(like),
                KnowledgeEntry.tags.ilike(like),
            )
        )
        .order_by(KnowledgeEntry.views.desc(), KnowledgeEntry.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/similar", response_model=list[KnowledgeEntryOut])
def similar_entries(
    equipment_id: Optional[int] = None,
    fault_category: Optional[str] = None,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """相似案例推荐：按 equipment_id 和/或 fault_category 匹配，
    优先返回同设备同分类，其次同设备或同分类，按复发次数/浏览量倒序。"""
    q = db.query(KnowledgeEntry).filter(KnowledgeEntry.status == "active")
    if equipment_id is not None and fault_category:
        # 同设备 + 同分类 优先
        rows = (
            q.filter(
                KnowledgeEntry.equipment_id == equipment_id,
                KnowledgeEntry.fault_category == fault_category,
            )
            .order_by(KnowledgeEntry.recurrence_count.desc(), KnowledgeEntry.views.desc())
            .offset(skip).limit(limit).all()
        )
        if rows:
            return rows
        # 退化为同设备 或 同分类
        rows = (
            q.filter(
                or_(
                    KnowledgeEntry.equipment_id == equipment_id,
                    KnowledgeEntry.fault_category == fault_category,
                )
            )
            .order_by(KnowledgeEntry.recurrence_count.desc(), KnowledgeEntry.views.desc())
            .offset(skip).limit(limit).all()
        )
        return rows
    if equipment_id is not None:
        return (
            q.filter(KnowledgeEntry.equipment_id == equipment_id)
            .order_by(KnowledgeEntry.recurrence_count.desc(), KnowledgeEntry.views.desc())
            .offset(skip).limit(limit).all()
        )
    if fault_category:
        return (
            q.filter(KnowledgeEntry.fault_category == fault_category)
            .order_by(KnowledgeEntry.recurrence_count.desc(), KnowledgeEntry.views.desc())
            .offset(skip).limit(limit).all()
        )
    return (
        q.order_by(KnowledgeEntry.recurrence_count.desc(), KnowledgeEntry.views.desc())
        .offset(skip).limit(limit).all()
    )


@router.get("/{entry_id}", response_model=KnowledgeEntryOut)
def get_entry(entry_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """知识详情，浏览量 +1。"""
    obj = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    obj.views = (obj.views or 0) + 1
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{entry_id}", response_model=KnowledgeEntryOut)
def update_entry(
    entry_id: int, obj_in: KnowledgeEntryUpdate,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    obj = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    obj = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/{entry_id}/recurrence", response_model=KnowledgeEntryOut)
def mark_recurrence(entry_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """标记复发，recurrence_count +1。"""
    obj = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    obj.recurrence_count = (obj.recurrence_count or 0) + 1
    db.commit()
    db.refresh(obj)
    return obj
