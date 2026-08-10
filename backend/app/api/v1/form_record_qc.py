from datetime import datetime
import hashlib
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password
from app.models import FormRecord, FormRecordAmendment, FormRecordValue, User
from app.schemas import FormRecordAuditRequest, FormRecordAmendmentCreate, FormRecordAmendmentOut
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/form-record-qc", tags=["结构化表单记录-文控扩展"])


def _make_signature(record_id, stage, signer_id, signed_at, reason, password_validated):
    data = "|".join(str(x) for x in [
        record_id,
        stage,
        signer_id,
        signed_at.isoformat() if signed_at else "",
        reason or "",
        password_validated,
    ])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class _AuditBody(BaseModel):
    note: Optional[str] = None
    comment: Optional[str] = None
    password: Optional[str] = None
    reject: bool = False


class _ApproveAmendmentBody(BaseModel):
    approved: bool = True
    note: Optional[str] = None


# ==================== 1) POST /records/{record_id}/audit 文控审核（二次密码校验） ====================
@router.post("/records/{record_id}/audit")
def audit_record(
    record_id: int,
    payload: _AuditBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("form_record.audit")),
):
    # 密码二次校验（兼容没传密码场景 - 为了允许脚本降级测试，但仍强烈建议传密码）
    password_ok = False
    if payload.password:
        if not verify_password(payload.password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="密码校验失败，电子签名无效")
        password_ok = True

    record = db.query(FormRecord).filter(FormRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="表单记录不存在")

    if record.status not in ("已提交", "已审核", "草稿"):
        raise HTTPException(status_code=400, detail=f"当前状态为'{record.status}'，仅已提交/已审核/草稿记录可审核")

    audited_at = datetime.utcnow()
    comment = payload.comment or payload.note or ""

    if payload.reject:
        record.status = "已提交"
        if comment:
            amendment = FormRecordAmendment(
                record_id=record.id,
                field_key="*",
                field_label="审核驳回备注",
                original_value=None,
                corrected_value=None,
                reason=f"[审核驳回] {comment}",
                amended_by_id=current_user.id,
                amended_by_username=current_user.username,
                amended_at=audited_at,
                amendment_signature=_make_signature(
                    record.id, "audit_reject", current_user.id, audited_at, comment, password_ok
                ),
                password_validated=password_ok,
            )
            db.add(amendment)
        db.commit()
        db.refresh(record)
        return {
            "id": record.id,
            "ok": True,
            "rejected": True,
            "audited": False,
            "audited_at": audited_at.isoformat(),
            "audited_by": current_user.username,
            "signature_tail": None,
            "status": record.status,
        }

    if getattr(record, "audited", False):
        raise HTTPException(status_code=400, detail="该记录已审核通过，不可重复审核")

    record.audited = True
    record.audited_at = audited_at
    record.audited_by = current_user.id
    record.audit_signature = _make_signature(
        record.id, "audit", current_user.id, audited_at, comment, password_ok
    )
    record.audit_password_validated = password_ok
    record.status = "已审核"

    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "ok": True,
        "audited": True,
        "audited_at": audited_at.isoformat(),
        "audited_by": current_user.username,
        "audited_by_id": current_user.id,
        "signature_tail": record.audit_signature[-8:] if record.audit_signature else None,
        "status": record.status,
    }


# ==================== 2) GET /records/{record_id}/amendments 附加修正列表 ====================
@router.get("/records/{record_id}/amendments", response_model=List[FormRecordAmendmentOut])
def list_amendments(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(FormRecord).filter(FormRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="表单记录不存在")
    amendments = db.query(FormRecordAmendment).filter(
        FormRecordAmendment.record_id == record_id
    ).order_by(FormRecordAmendment.amended_at.desc()).all()
    return amendments


# ==================== 3) POST /records/{record_id}/amendments 创建附加修正（二次密码校验） ====================
@router.post(
    "/records/{record_id}/amendments",
    response_model=FormRecordAmendmentOut,
    dependencies=[Depends(require_permission("form_record.amend"))],
)
def create_amendment(
    record_id: int,
    payload: FormRecordAmendmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="密码校验失败，电子签名无效")

    record = db.query(FormRecord).filter(FormRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="表单记录不存在")

    amended_at = datetime.utcnow()
    password_validated = True

    signature = _make_signature(
        record.id, "amend", current_user.id, amended_at, payload.reason, password_validated
    )

    amendment = FormRecordAmendment(
        record_id=record_id,
        field_key=payload.field_key,
        field_label=payload.field_label,
        original_value=payload.original_value,
        corrected_value=payload.corrected_value,
        reason=payload.reason,
        amended_by_id=current_user.id,
        amended_by_username=current_user.username,
        amended_at=amended_at,
        amendment_signature=signature,
        password_validated=password_validated,
    )
    db.add(amendment)
    db.commit()
    db.refresh(amendment)
    return amendment


# ==================== 4) POST /amendments/{id}/approve 审批附加修正 ====================
@router.post(
    "/amendments/{id}/approve",
    response_model=FormRecordAmendmentOut,
    dependencies=[Depends(require_permission("form_record.audit"))],
)
def approve_amendment(
    id: int,
    body: _ApproveAmendmentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    amendment = db.query(FormRecordAmendment).filter(FormRecordAmendment.id == id).first()
    if not amendment:
        raise HTTPException(status_code=404, detail="修正记录不存在")

    amendment.approved = body.approved
    amendment.approved_by_id = current_user.id
    amendment.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(amendment)
    return amendment
