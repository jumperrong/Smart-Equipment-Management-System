"""首件检验（FAI）服务。

状态机：DRAFT -> PENDING_QA -> APPROVED / REJECTED
场景：换型/换班首件须 QA 签核后才能批量生产；绑定到 Dispatch。
"""
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import (
    FirstArticleInspection, FAIStatus,
    Dispatch, ProductionOrder,
)
from app.schemas import FAICreate, FAIUpdate, FAIReview


def _gen_fai_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%y%m%d")
    prefix = f"FAI-{today}-"
    count = db.query(FirstArticleInspection).filter(
        FirstArticleInspection.fai_no.like(f"{prefix}%")
    ).count()
    return f"{prefix}{count + 1:04d}"


def list_fais(
    db: Session,
    status: str | None = None,
    dispatch_id: int | None = None,
    mo_id: int | None = None,
    product_id: int | None = None,
    reviewer_id: int | None = None,
    keyword: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    q = db.query(FirstArticleInspection)
    if status:
        q = q.filter(FirstArticleInspection.status == status)
    if dispatch_id:
        q = q.filter(FirstArticleInspection.dispatch_id == dispatch_id)
    if mo_id:
        q = q.filter(FirstArticleInspection.mo_id == mo_id)
    if product_id:
        q = q.filter(FirstArticleInspection.product_id == product_id)
    if reviewer_id:
        q = q.filter(FirstArticleInspection.reviewed_by_id == reviewer_id)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (FirstArticleInspection.fai_no.like(kw))
            | (FirstArticleInspection.conclusion.like(kw))
        )
    return q.order_by(FirstArticleInspection.id.desc()).offset(skip).limit(limit).all()


def get_fai(db: Session, fai_id: int) -> FirstArticleInspection:
    fai = db.query(FirstArticleInspection).filter(FirstArticleInspection.id == fai_id).first()
    if not fai:
        raise HTTPException(404, f"FAI id={fai_id} 不存在")
    return fai


def get_fai_by_dispatch(db: Session, dispatch_id: int) -> FirstArticleInspection | None:
    return (
        db.query(FirstArticleInspection)
        .filter(FirstArticleInspection.dispatch_id == dispatch_id)
        .first()
    )


def create_fai(
    db: Session,
    obj_in: FAICreate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> FirstArticleInspection:
    # 校验派工存在
    d = db.query(Dispatch).filter(Dispatch.id == obj_in.dispatch_id).first()
    if not d:
        raise HTTPException(404, f"派工 id={obj_in.dispatch_id} 不存在")

    # 避免重复：同一派工只能有一份 FAI
    existing = get_fai_by_dispatch(db, obj_in.dispatch_id)
    if existing:
        raise HTTPException(400, f"派工 id={obj_in.dispatch_id} 已存在 FAI（{existing.fai_no}）")

    # 从派工自动带出 mo_id / product_id / equipment_id
    mo_id = d.mo_id
    equipment_id = d.equipment_id
    product_id = None
    if mo_id:
        mo = db.query(ProductionOrder).filter(ProductionOrder.id == mo_id).first()
        if mo:
            product_id = mo.product_id

    fai_no = _gen_fai_no(db)
    fai = FirstArticleInspection(
        fai_no=fai_no,
        dispatch_id=obj_in.dispatch_id,
        mo_id=mo_id,
        product_id=product_id,
        equipment_id=equipment_id,
        change_type=obj_in.change_type,
        sample_qty=obj_in.sample_qty,
        inspection_data=obj_in.inspection_data,
        conclusion=obj_in.conclusion,
        status=FAIStatus.DRAFT.value,
    )
    db.add(fai)
    db.commit()
    db.refresh(fai)
    return fai


def update_fai(db: Session, fai: FirstArticleInspection, obj_in: FAIUpdate) -> FirstArticleInspection:
    if fai.status not in (FAIStatus.DRAFT.value, FAIStatus.PENDING_QA.value):
        raise HTTPException(400, f"FAI 状态为 {fai.status}，不可修改（仅 DRAFT/PENDING_QA 可改）")
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in data.items():
        setattr(fai, k, v)
    db.commit()
    db.refresh(fai)
    return fai


def submit_fai(
    db: Session,
    fai: FirstArticleInspection,
    user_id: int | None = None,
    user_name: str | None = None,
) -> FirstArticleInspection:
    """提交：DRAFT -> PENDING_QA。"""
    if fai.status != FAIStatus.DRAFT.value:
        raise HTTPException(400, f"FAI 状态为 {fai.status}，仅 DRAFT 可提交")
    fai.status = FAIStatus.PENDING_QA.value
    fai.submitted_at = datetime.utcnow()
    fai.submitted_by_id = user_id
    fai.submitted_by_name = user_name
    db.commit()
    db.refresh(fai)
    return fai


def review_fai(
    db: Session,
    fai: FirstArticleInspection,
    obj_in: FAIReview,
    user_id: int | None = None,
    user_name: str | None = None,
) -> FirstArticleInspection:
    """QA 签核：必须 PENDING_QA；disposition=APPROVED/REJECTED。"""
    if fai.status != FAIStatus.PENDING_QA.value:
        raise HTTPException(400, f"FAI 状态为 {fai.status}，仅 PENDING_QA 可签核")
    if obj_in.disposition not in (FAIStatus.APPROVED.value, FAIStatus.REJECTED.value):
        raise HTTPException(400, f"未知处置方式: {obj_in.disposition}（可选 APPROVED/REJECTED）")

    if obj_in.disposition == FAIStatus.APPROVED.value:
        fai.status = FAIStatus.APPROVED.value
    else:
        fai.status = FAIStatus.REJECTED.value
        fai.reject_reason = obj_in.reject_reason
    fai.reviewed_at = datetime.utcnow()
    fai.reviewed_by_id = user_id
    fai.reviewed_by_name = user_name
    fai.review_remark = obj_in.review_remark
    db.commit()
    db.refresh(fai)
    return fai


def delete_fai(db: Session, fai: FirstArticleInspection):
    """删除：仅 DRAFT 状态可删。"""
    if fai.status != FAIStatus.DRAFT.value:
        raise HTTPException(400, f"FAI 状态为 {fai.status}，不可删除（仅 DRAFT 可删）")
    db.delete(fai)
    db.commit()
