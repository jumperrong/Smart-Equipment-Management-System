"""文档编号规则管理 API（体系文控用）。

功能：
- 编号规则 CRUD（每个文控分类一条规则）
- 根据规则 + 机台生成文档编号（next_seq 自增）
- 预览编号格式（不消耗流水号）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import DocNoRule, Equipment
from app.schemas import (
    DocNoRuleOut,
    DocNoRuleCreate,
    DocNoRuleUpdate,
    DocNoGenerateRequest,
    DocNoGenerateResponse,
)
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/doc-no-rules", tags=["文档编号规则"])

# 文控分类枚举
DOC_CLASSES = ["SOP", "SIP", "SPEC", "FORM", "RECORD", "EXTERN"]
DOC_CLASS_LABELS = {
    "SOP": "SOP 作业指导书",
    "SIP": "SIP 检验标准",
    "SPEC": "SPEC 规格书",
    "FORM": "FORM 表单模板",
    "RECORD": "RECORD 作业记录",
    "EXTERN": "EXTERN 外来文件",
}


def _build_doc_no(rule: DocNoRule, equipment: Optional[Equipment] = None, seq: Optional[int] = None) -> str:
    """根据规则构建编号字符串（不修改 next_seq）。

    格式：{prefix}[-{year}][-{month}][-{equipment_code}]-{seq:0{seq_width}d}
    """
    parts = [rule.prefix]
    now = datetime.utcnow()
    if rule.use_year:
        parts.append(f"{now.year}")
    if rule.use_month:
        parts.append(f"{now.month:02d}")
    if rule.use_equipment_code and equipment:
        code = equipment.asset_no or equipment.name or str(equipment.id)
        parts.append(code)
    s = seq if seq is not None else rule.next_seq
    parts.append(f"{s:0{rule.seq_width}d}")
    return "-".join(parts)


# ==================== 列表 ====================

@router.get("", response_model=list[DocNoRuleOut])
def list_doc_no_rules(db: Session = Depends(get_db)):
    rules = db.query(DocNoRule).order_by(DocNoRule.doc_class).all()
    return rules


# ==================== 创建 ====================

@router.post("", response_model=DocNoRuleOut, dependencies=[Depends(require_permission("system.settings_manage"))])
def create_doc_no_rule(payload: DocNoRuleCreate, db: Session = Depends(get_db)):
    if payload.doc_class not in DOC_CLASSES:
        raise HTTPException(status_code=400, detail=f"doc_class 取值: {', '.join(DOC_CLASSES)}")
    existing = db.query(DocNoRule).filter(DocNoRule.doc_class == payload.doc_class).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"分类 {payload.doc_class} 的编号规则已存在")
    rule = DocNoRule(
        doc_class=payload.doc_class,
        prefix=payload.prefix,
        use_equipment_code=payload.use_equipment_code,
        use_year=payload.use_year,
        use_month=payload.use_month,
        seq_width=payload.seq_width,
        next_seq=1,
        is_active=payload.is_active,
        description=payload.description,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


# ==================== 更新 ====================

@router.put("/{rule_id}", response_model=DocNoRuleOut, dependencies=[Depends(require_permission("system.settings_manage"))])
def update_doc_no_rule(rule_id: int, payload: DocNoRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(DocNoRule).filter(DocNoRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="编号规则不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


# ==================== 删除 ====================

@router.delete("/{rule_id}", dependencies=[Depends(require_permission("system.settings_manage"))])
def delete_doc_no_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(DocNoRule).filter(DocNoRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="编号规则不存在")
    db.delete(rule)
    db.commit()
    return {"ok": True}


# ==================== 生成编号（消耗流水号） ====================

@router.post("/generate", response_model=DocNoGenerateResponse, dependencies=[Depends(require_permission("process_doc.write"))])
def generate_doc_no(payload: DocNoGenerateRequest, db: Session = Depends(get_db)):
    """根据规则生成文档编号，next_seq 自增。

    - 找不到规则或规则已停用 → 返回 404
    - 规则含 use_equipment_code 但未传 equipment_id → 返回 400
    """
    rule = db.query(DocNoRule).filter(
        DocNoRule.doc_class == payload.doc_class,
        DocNoRule.is_active == True,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"分类 {payload.doc_class} 未配置编号规则或已停用")

    equipment = None
    if rule.use_equipment_code:
        if not payload.equipment_id:
            raise HTTPException(status_code=400, detail="该编号规则要求包含机台码，请先选择机台")
        equipment = db.query(Equipment).filter(Equipment.id == payload.equipment_id).first()
        if not equipment:
            raise HTTPException(status_code=404, detail="设备不存在")

    seq = rule.next_seq
    doc_no = _build_doc_no(rule, equipment, seq)
    rule.next_seq = seq + 1
    db.commit()
    return DocNoGenerateResponse(doc_no=doc_no, rule_id=rule.id, seq=seq)


# ==================== 预览编号（不消耗流水号） ====================

@router.get("/preview", response_model=DocNoGenerateResponse)
def preview_doc_no(
    doc_class: str,
    equipment_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """预览编号格式（不消耗流水号），用于前端实时展示。"""
    rule = db.query(DocNoRule).filter(DocNoRule.doc_class == doc_class).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"分类 {doc_class} 未配置编号规则")
    equipment = None
    if rule.use_equipment_code and equipment_id:
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    doc_no = _build_doc_no(rule, equipment, rule.next_seq)
    return DocNoGenerateResponse(doc_no=doc_no, rule_id=rule.id, seq=rule.next_seq)
