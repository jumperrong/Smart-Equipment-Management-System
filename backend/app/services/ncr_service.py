"""不合格品报告（NCR）服务。

状态机：OPEN -> UNDER_REVIEW -> DISPOSITIONED -> CLOSED
评审联动：disposition=SCRAP 时，关联 lot 状态置 SCRAPPED；
        disposition=REWORK 时，关联 lot 状态保持 IN_WIP（等待返工派工）。
"""
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import (
    NonConformanceReport, NCRStatus, NCRSeverity, NCRDisposition,
    Lot, LotStatus, LaborReport, Dispatch, ProductionOrder, Product, User,
)
from app.schemas import NCRCreate, NCRUpdate, NCRReview


def _gen_ncr_no(db: Session) -> str:
    today = datetime.utcnow().strftime("%y%m%d")
    prefix = f"NCR-{today}-"
    count = db.query(NonConformanceReport).filter(NonConformanceReport.ncr_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def list_ncrs(
    db: Session,
    status: str | None = None,
    severity: str | None = None,
    lot_id: int | None = None,
    mo_id: int | None = None,
    dispatch_id: int | None = None,
    labor_report_id: int | None = None,
    keyword: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    q = db.query(NonConformanceReport)
    if status:
        q = q.filter(NonConformanceReport.status == status)
    if severity:
        q = q.filter(NonConformanceReport.severity == severity)
    if lot_id:
        q = q.filter(NonConformanceReport.lot_id == lot_id)
    if mo_id:
        q = q.filter(NonConformanceReport.mo_id == mo_id)
    if dispatch_id:
        q = q.filter(NonConformanceReport.dispatch_id == dispatch_id)
    if labor_report_id:
        q = q.filter(NonConformanceReport.labor_report_id == labor_report_id)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (NonConformanceReport.ncr_no.like(kw))
            | (NonConformanceReport.title.like(kw))
            | (NonConformanceReport.defect_code.like(kw))
        )
    return q.order_by(NonConformanceReport.id.desc()).offset(skip).limit(limit).all()


def get_ncr(db: Session, ncr_id: int) -> NonConformanceReport:
    ncr = db.query(NonConformanceReport).filter(NonConformanceReport.id == ncr_id).first()
    if not ncr:
        raise HTTPException(404, f"NCR id={ncr_id} 不存在")
    return ncr


def create_ncr(
    db: Session,
    obj_in: NCRCreate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> NonConformanceReport:
    # 校验关联对象
    if obj_in.labor_report_id:
        lr = db.query(LaborReport).filter(LaborReport.id == obj_in.labor_report_id).first()
        if not lr:
            raise HTTPException(404, f"报工记录 id={obj_in.labor_report_id} 不存在")
        # 若未指定 dispatch/mo/product，从报工自动带出
        if not obj_in.dispatch_id and lr.dispatch_id:
            obj_in.dispatch_id = lr.dispatch_id
        if not obj_in.lot_id:
            # 尝试从派工找到 lot
            from app.services.lot_service import list_lots
            lots = list_lots(db, mo_id=None, limit=200)
            for lot in lots:
                if lot.origin_dispatch_id == lr.dispatch_id:
                    obj_in.lot_id = lot.id
                    break
    if obj_in.dispatch_id:
        d = db.query(Dispatch).filter(Dispatch.id == obj_in.dispatch_id).first()
        if not d:
            raise HTTPException(404, f"派工 id={obj_in.dispatch_id} 不存在")
        if not obj_in.mo_id:
            obj_in.mo_id = d.mo_id
    if obj_in.mo_id:
        mo = db.query(ProductionOrder).filter(ProductionOrder.id == obj_in.mo_id).first()
        if not mo:
            raise HTTPException(404, f"生产订单 id={obj_in.mo_id} 不存在")
        if not obj_in.product_id:
            obj_in.product_id = mo.product_id
    if obj_in.lot_id:
        lot = db.query(Lot).filter(Lot.id == obj_in.lot_id).first()
        if not lot:
            raise HTTPException(404, f"批次 id={obj_in.lot_id} 不存在")
        if not obj_in.product_id:
            obj_in.product_id = lot.product_id
    if obj_in.product_id:
        p = db.query(Product).filter(Product.id == obj_in.product_id).first()
        if not p:
            raise HTTPException(404, f"产品 id={obj_in.product_id} 不存在")

    # 严重度枚举校验
    valid_severity = {e.value for e in NCRSeverity}
    if obj_in.severity not in valid_severity:
        raise HTTPException(400, f"未知严重度: {obj_in.severity}（可选 {','.join(valid_severity)}）")

    ncr_no = _gen_ncr_no(db)
    ncr = NonConformanceReport(
        ncr_no=ncr_no,
        title=obj_in.title,
        source_type=obj_in.source_type,
        source_ref_id=obj_in.source_ref_id,
        labor_report_id=obj_in.labor_report_id,
        dispatch_id=obj_in.dispatch_id,
        mo_id=obj_in.mo_id,
        lot_id=obj_in.lot_id,
        product_id=obj_in.product_id,
        defect_code=obj_in.defect_code,
        defect_description=obj_in.defect_description,
        defect_qty=obj_in.defect_qty,
        severity=obj_in.severity,
        status=NCRStatus.OPEN.value,
        disposition=NCRDisposition.PENDING.value,
        reporter_id=user_id,
        reporter_name=user_name,
    )
    db.add(ncr)
    db.flush()

    # 联动 lot 置 ON_HOLD
    if ncr.lot_id:
        lot = db.query(Lot).filter(Lot.id == ncr.lot_id).first()
        if lot and lot.status == LotStatus.IN_WIP.value:
            lot.status = LotStatus.ON_HOLD.value
            lot.hold_reason = f"NCR#{ncr.id} 待评审"
            lot.ncr_id = ncr.id

    db.commit()
    db.refresh(ncr)
    return ncr


def update_ncr(db: Session, ncr: NonConformanceReport, obj_in: NCRUpdate) -> NonConformanceReport:
    if ncr.status == NCRStatus.CLOSED.value:
        raise HTTPException(400, "NCR 已结案，不可修改")
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in data.items():
        setattr(ncr, k, v)
    db.commit()
    db.refresh(ncr)
    return ncr


def review_ncr(
    db: Session,
    ncr: NonConformanceReport,
    obj_in: NCRReview,
    user_id: int | None = None,
    user_name: str | None = None,
) -> NonConformanceReport:
    """评审：进入 UNDER_REVIEW，再判定 disposition + root_cause。"""
    if ncr.status == NCRStatus.CLOSED.value:
        raise HTTPException(400, "NCR 已结案，不可评审")

    valid_disp = {e.value for e in NCRDisposition}
    if obj_in.disposition not in valid_disp:
        raise HTTPException(400, f"未知处置方式: {obj_in.disposition}")

    # 第一次评审：状态从 OPEN -> UNDER_REVIEW，写入 reviewer
    if ncr.status == NCRStatus.OPEN.value:
        ncr.status = NCRStatus.UNDER_REVIEW.value
        ncr.reviewer_id = user_id
        ncr.reviewer_name = user_name
        ncr.review_time = datetime.utcnow()

    # 给定 disposition（非 PENDING）则升级为 DISPOSITIONED
    if obj_in.disposition and obj_in.disposition != NCRDisposition.PENDING.value:
        ncr.status = NCRStatus.DISPOSITIONED.value
        ncr.disposition = obj_in.disposition
        ncr.reviewer_id = user_id or ncr.reviewer_id
        ncr.reviewer_name = user_name or ncr.reviewer_name
        ncr.review_time = datetime.utcnow()
        ncr.review_remark = obj_in.review_remark

        if obj_in.severity:
            ncr.severity = obj_in.severity
        if obj_in.root_cause:
            ncr.root_cause = obj_in.root_cause
        if obj_in.corrective_action:
            ncr.corrective_action = obj_in.corrective_action

        # 联动 lot 处置
        if ncr.lot_id:
            lot = db.query(Lot).filter(Lot.id == ncr.lot_id).first()
            if lot:
                if obj_in.disposition == NCRDisposition.SCRAP.value:
                    lot.status = LotStatus.SCRAPPED.value
                    lot.hold_reason = f"NCR#{ncr.id} 评审报废"
                elif obj_in.disposition == NCRDisposition.REWORK.value:
                    lot.status = LotStatus.IN_WIP.value
                    lot.hold_reason = f"NCR#{ncr.id} 返工待派"
                elif obj_in.disposition == NCRDisposition.USE_AS_IS.value:
                    lot.status = LotStatus.IN_WIP.value
                    lot.hold_reason = f"NCR#{ncr.id} 让步接收"
                elif obj_in.disposition == NCRDisposition.RETURN_TO_VENDOR.value:
                    lot.status = LotStatus.ON_HOLD.value
                    lot.hold_reason = f"NCR#{ncr.id} 退供应商"

    db.commit()
    db.refresh(ncr)
    return ncr


def close_ncr(
    db: Session,
    ncr: NonConformanceReport,
    user_id: int | None = None,
    user_name: str | None = None,
) -> NonConformanceReport:
    """结案：必须先 DISPOSITIONED。"""
    if ncr.status != NCRStatus.DISPOSITIONED.value:
        raise HTTPException(400, f"NCR 当前状态 {ncr.status}，必须先评审处置后才能结案")
    ncr.status = NCRStatus.CLOSED.value
    ncr.closed_by_id = user_id
    ncr.closed_by_name = user_name
    ncr.closed_at = datetime.utcnow()
    # 联动 lot 解除 hold
    if ncr.lot_id:
        lot = db.query(Lot).filter(Lot.id == ncr.lot_id).first()
        if lot and lot.status == LotStatus.ON_HOLD.value:
            lot.status = LotStatus.IN_WIP.value
            lot.hold_reason = None
    db.commit()
    db.refresh(ncr)
    return ncr


def delete_ncr(db: Session, ncr: NonConformanceReport):
    """删除：仅 OPEN 状态可删。"""
    if ncr.status != NCRStatus.OPEN.value:
        raise HTTPException(400, f"NCR 状态为 {ncr.status}，不可删除（仅 OPEN 可删）")
    # 解除 lot 关联
    if ncr.lot_id:
        lot = db.query(Lot).filter(Lot.id == ncr.lot_id).first()
        if lot and lot.ncr_id == ncr.id:
            lot.ncr_id = None
            if lot.status == LotStatus.ON_HOLD.value:
                lot.status = LotStatus.IN_WIP.value
                lot.hold_reason = None
    db.delete(ncr)
    db.commit()
