from datetime import datetime, timedelta
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Union

from app.core.database import get_db
from app.core.security import verify_password
from app.models import User, ProcessDocument, DocumentApproval, DocumentChangeLog, DocumentDistribution
from app.schemas import (
    ApprovalSignRequest,
    DocumentApprovalOut,
    DocumentChangeLogCreate,
    DocumentChangeLogOut,
    DocumentDistributionCreate,
    DocumentDistributionOut,
    DocumentDistributionReturn,
    ProcessDocumentOut,
)
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission, is_allowed

router = APIRouter(prefix="/process-doc-qc", tags=["工艺文件-文控扩展"])


def _make_signature(doc_id, stage, signer_id, signed_at, comment, password_validated):
    data = "|".join(str(x) for x in [
        doc_id,
        stage,
        signer_id,
        signed_at.isoformat() if signed_at else "",
        comment or "",
        password_validated,
    ])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _compute_next_review(effective_date, cycle_month):
    if not cycle_month or cycle_month <= 0:
        return None
    base = effective_date or datetime.utcnow()
    total_days = int(cycle_month * 30.44)
    return base + timedelta(days=total_days)


# ==================== 1) POST /approvals/sign ====================

@router.post("/approvals/sign", response_model=DocumentApprovalOut)
def approval_sign(
    payload: ApprovalSignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="密码校验失败，电子签名无效")

    doc = db.query(ProcessDocument).filter(ProcessDocument.id == payload.process_document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="工艺文件不存在")

    stage = payload.stage
    comment = payload.comment
    signed_at = datetime.utcnow()
    password_validated = True
    signer_display_name = getattr(current_user, "display_name", None) or getattr(current_user, "full_name", "") or ""

    result = "approved"
    stage_order = 1
    new_status = None

    if stage == "prepare":
        if not is_allowed(db, current_user.role, "process_doc.submit_review"):
            raise HTTPException(status_code=403, detail="权限不足")
        if doc.status != "草稿":
            raise HTTPException(status_code=400, detail=f"当前状态为'{doc.status}'，仅草稿可提交审核")
        stage_order = 1
        new_status = "审核中"

    elif stage == "review":
        if not is_allowed(db, current_user.role, "process_doc.approve"):
            raise HTTPException(status_code=403, detail="权限不足")
        if doc.status != "审核中":
            raise HTTPException(status_code=400, detail=f"当前状态为'{doc.status}'，仅审核中可执行审核")
        existing_review = db.query(DocumentApproval).filter(
            DocumentApproval.process_document_id == doc.id,
            DocumentApproval.stage == "review",
            DocumentApproval.result == "approved",
        ).first()
        if existing_review:
            raise HTTPException(status_code=400, detail="审核已通过，不可重复审核")
        stage_order = 2

    elif stage == "approve":
        if not is_allowed(db, current_user.role, "process_doc.approve"):
            raise HTTPException(status_code=403, detail="权限不足")
        if doc.status != "审核中":
            raise HTTPException(status_code=400, detail=f"当前状态为'{doc.status}'，仅审核中可执行批准")
        review_passed = db.query(DocumentApproval).filter(
            DocumentApproval.process_document_id == doc.id,
            DocumentApproval.stage == "review",
            DocumentApproval.result == "approved",
        ).first()
        if not review_passed:
            raise HTTPException(status_code=400, detail="审核尚未通过，不可批准")
        stage_order = 3
        new_status = "生效"

        eff_dt = doc.effective_date or signed_at
        doc.effective_date = eff_dt
        doc.next_review_date = _compute_next_review(eff_dt, doc.review_cycle_month)

        db.query(ProcessDocument).filter(
            ProcessDocument.group_id == doc.group_id,
            ProcessDocument.id != doc.id,
            ProcessDocument.status == "生效",
        ).update({ProcessDocument.status: "作废"}, synchronize_session=False)

    elif stage == "reject_prepare":
        if not is_allowed(db, current_user.role, "process_doc.submit_review"):
            raise HTTPException(status_code=403, detail="权限不足")
        if not comment:
            raise HTTPException(status_code=400, detail="驳回时必须填写原因(comment)")
        result = "rejected"
        stage_order = 1
        new_status = "草稿"

    elif stage == "reject_review":
        if not is_allowed(db, current_user.role, "process_doc.approve"):
            raise HTTPException(status_code=403, detail="权限不足")
        if not comment:
            raise HTTPException(status_code=400, detail="驳回时必须填写原因(comment)")
        result = "rejected"
        stage_order = 2
        new_status = "草稿"

    else:
        raise HTTPException(status_code=400, detail=f"未知 stage: {stage}")

    signature = _make_signature(doc.id, stage, current_user.id, signed_at, comment, password_validated)

    approval = DocumentApproval(
        process_document_id=doc.id,
        stage=stage,
        stage_order=stage_order,
        result=result,
        comment=comment,
        signer_id=current_user.id,
        signer_username=current_user.username,
        signer_display_name=signer_display_name,
        signer_role=current_user.role,
        signed_at=signed_at,
        signature=signature,
        password_validated=password_validated,
    )
    db.add(approval)

    if new_status:
        doc.status = new_status

    db.commit()
    db.refresh(approval)

    approval_out = DocumentApprovalOut.model_validate(approval)
    approval_out.signature_tail = approval.signature[-8:] if approval.signature else None
    return approval_out


# ==================== 2) GET /{doc_id}/approvals ====================

@router.get("/{doc_id}/approvals", response_model=List[DocumentApprovalOut])
def list_approvals(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    approvals = db.query(DocumentApproval).filter(
        DocumentApproval.process_document_id == doc_id
    ).order_by(DocumentApproval.stage_order.asc(), DocumentApproval.signed_at.asc()).all()
    result = []
    for a in approvals:
        out = DocumentApprovalOut.model_validate(a)
        out.signature_tail = a.signature[-8:] if a.signature else None
        result.append(out)
    return result


# ==================== 3) POST /change-logs ====================

@router.post(
    "/change-logs",
    response_model=DocumentChangeLogOut,
    dependencies=[Depends(require_permission("process_doc.write"))],
)
def create_change_log(
    payload: DocumentChangeLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(ProcessDocument).filter(ProcessDocument.id == payload.process_document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    detail_items_json = None
    if payload.detail_items:
        items_list = [item.model_dump() for item in payload.detail_items]
        detail_items_json = items_list
    log = DocumentChangeLog(
        process_document_id=payload.process_document_id,
        change_reason=payload.change_reason,
        change_summary=payload.change_summary,
        detail_items_json=detail_items_json,
        created_by_id=current_user.id,
        created_by_username=current_user.username,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ==================== 4) GET /{doc_id}/change-logs ====================

@router.get("/{doc_id}/change-logs", response_model=List[DocumentChangeLogOut])
def list_change_logs(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    logs = db.query(DocumentChangeLog).filter(
        DocumentChangeLog.process_document_id == doc_id
    ).order_by(DocumentChangeLog.created_at.desc()).all()
    return logs


# ==================== 5) POST /distributions ====================

@router.post(
    "/distributions",
    response_model=List[DocumentDistributionOut],
    dependencies=[Depends(require_permission("process_doc.approve"))],
)
def create_distributions(
    payload: Union[DocumentDistributionCreate, List[DocumentDistributionCreate]],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = payload if isinstance(payload, list) else [payload]
    created = []
    for item in items:
        doc = db.query(ProcessDocument).filter(ProcessDocument.id == item.process_document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"工艺文件 {item.process_document_id} 不存在")
        dist = DocumentDistribution(
            process_document_id=item.process_document_id,
            recipient_type=item.recipient_type,
            recipient_ref=item.recipient_ref,
            hold_copies=item.hold_copies,
            medium=item.medium,
            issued_by_id=current_user.id,
        )
        db.add(dist)
        created.append(dist)
    db.commit()
    for d in created:
        db.refresh(d)
    result = []
    for d in created:
        out = DocumentDistributionOut.model_validate(d)
        if out.distributed_by_username is None and d.issued_by_id:
            u = db.query(User).filter(User.id == d.issued_by_id).first()
            out.distributed_by_username = u.username if u else f"#{d.issued_by_id}"
        result.append(out)
    return result


# ==================== 6) GET /{doc_id}/distributions ====================

@router.get("/{doc_id}/distributions", response_model=List[DocumentDistributionOut])
def list_distributions(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    dists = db.query(DocumentDistribution).filter(
        DocumentDistribution.process_document_id == doc_id
    ).order_by(DocumentDistribution.issued_at.desc()).all()
    result = []
    for d in dists:
        out = DocumentDistributionOut.model_validate(d)
        if out.distributed_by_username is None and d.issued_by_id:
            u = db.query(User).filter(User.id == d.issued_by_id).first()
            out.distributed_by_username = u.username if u else f"#{d.issued_by_id}"
        result.append(out)
    return result


# ==================== 7) POST /distributions/return-batch ====================

@router.post("/distributions/return-batch", response_model=List[DocumentDistributionOut])
def return_distributions_batch(
    payload: DocumentDistributionReturn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    updated = []
    for dist_id in payload.ids:
        dist = db.query(DocumentDistribution).filter(DocumentDistribution.id == dist_id).first()
        if not dist:
            continue
        dist.returned = True
        dist.returned_at = now
        dist.returned_by_id = current_user.id
        dist.return_note = payload.return_note
        updated.append(dist)
    db.commit()
    result = []
    for d in updated:
        db.refresh(d)
        out = DocumentDistributionOut.model_validate(d)
        if out.distributed_by_username is None and d.issued_by_id:
            u = db.query(User).filter(User.id == d.issued_by_id).first()
            out.distributed_by_username = u.username if u else f"#{d.issued_by_id}"
        result.append(out)
    return result


# ==================== 8) DELETE /distributions/{dist_id} ====================

@router.delete(
    "/distributions/{dist_id}",
    dependencies=[Depends(require_permission("process_doc.approve"))],
)
def delete_distribution(
    dist_id: int,
    db: Session = Depends(get_db),
):
    dist = db.query(DocumentDistribution).filter(DocumentDistribution.id == dist_id).first()
    if not dist:
        raise HTTPException(status_code=404, detail="分发明细不存在")
    db.delete(dist)
    db.commit()
    return {"ok": True}


# ==================== 9) GET /review-alerts ====================

@router.get("/review-alerts")
def review_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    threshold = now + timedelta(days=30)

    alerts_q = db.query(ProcessDocument).filter(
        ProcessDocument.status == "生效",
        ProcessDocument.next_review_date != None,
        ProcessDocument.next_review_date <= threshold,
    ).order_by(ProcessDocument.next_review_date.asc())
    alerts = alerts_q.all()

    count_draft = db.query(ProcessDocument).filter(ProcessDocument.status == "草稿").count()
    count_review = db.query(ProcessDocument).filter(ProcessDocument.status == "审核中").count()
    count_effective = db.query(ProcessDocument).filter(ProcessDocument.status == "生效").count()
    count_void = db.query(ProcessDocument).filter(ProcessDocument.status == "作废").count()
    count_alert = alerts_q.count()

    stats = {
        "草稿": count_draft,
        "审核中": count_review,
        "生效": count_effective,
        "作废": count_void,
        "复审到期": count_alert,
    }

    alerts_out = [ProcessDocumentOut.model_validate(a) for a in alerts]

    return {"stats": stats, "alerts": alerts_out}
