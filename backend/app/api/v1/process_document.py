"""工艺文件管理 API（与设备绑定，区别于设备维修保养附件）。

功能：
- 上传/下载/删除工艺文件
- 元数据编辑（名称、类型、说明等）
- 版本管理：同一文档可上传多个版本，共享 group_id，is_latest 标识最新
- 状态管理：草稿/生效/作废 流转（带合法性校验）
- 文件替换：保留元数据，替换实际文件内容
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ProcessDocument, Equipment
from app.schemas import (
    ProcessDocumentOut,
    ProcessDocumentUpdate,
    ProcessDocumentStatusTransition,
)
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/process-documents", tags=["工艺文件"])

# 允许的文件扩展名（白名单）
ALLOWED_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".zip", ".rar"}
# 单文件大小上限（50 MB）
MAX_FILE_SIZE = 50 * 1024 * 1024
# 允许的状态值
ALLOWED_STATUS = {"草稿", "生效", "作废"}
# 合法状态流转：(from, to)
VALID_TRANSITIONS = {
    ("草稿", "生效"),
    ("草稿", "作废"),
    ("生效", "作废"),
}


def _ensure_upload_dir():
    base = os.path.join(os.getcwd(), "data", "uploads", "process_docs")
    os.makedirs(base, exist_ok=True)
    return base


def _save_upload(file: UploadFile) -> tuple[str, int, str, str]:
    """保存上传文件，返回 (stored_name, file_size, file_type, ext)。

    校验扩展名与大小，生成随机存储名。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext and ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext}，仅允许: {', '.join(sorted(ALLOWED_EXTS))}",
        )
    stored_name = f"{uuid.uuid4().hex}{ext}"
    base = _ensure_upload_dir()
    stored_path = os.path.join(base, stored_name)
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大({len(content)}字节)，上限 {MAX_FILE_SIZE // 1024 // 1024} MB",
        )
    with open(stored_path, "wb") as f:
        f.write(content)
    return stored_name, len(content), file.content_type or "application/octet-stream", ext


def _delete_stored(stored_name: str) -> None:
    """安全删除存储文件。"""
    if not stored_name:
        return
    base = _ensure_upload_dir()
    fp = os.path.join(base, stored_name)
    if os.path.exists(fp):
        try:
            os.remove(fp)
        except OSError:
            pass


def _validate_transition(from_status: str, to_status: str) -> None:
    if to_status not in ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail=f"非法状态: {to_status}")
    if from_status == to_status:
        raise HTTPException(status_code=400, detail="目标状态与当前状态相同")
    if (from_status, to_status) not in VALID_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"非法状态流转: {from_status} → {to_status}。"
                  f"允许: 草稿→生效、草稿→作废、生效→作废",
        )


def backfill_version_meta(db: Session) -> int:
    """回填历史数据的版本元信息。

    对 group_id 为空的记录：每条生成唯一 group_id、version_seq=1、is_latest=True。
    返回回填条数。幂等：已回填的跳过。
    """
    rows = db.query(ProcessDocument).filter(
        (ProcessDocument.group_id == None) | (ProcessDocument.group_id == "")
    ).all()
    for r in rows:
        r.group_id = uuid.uuid4().hex
        r.version_seq = 1
        r.is_latest = True
    if rows:
        db.commit()
    return len(rows)


# ==================== 列表 ====================

@router.get("", response_model=list[ProcessDocumentOut])
def list_process_documents(
    equipment_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None, description="大类: guide指导性/record作业记录"),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None, description="作业记录-批号模糊查询"),
    keyword: Optional[str] = Query(None),
    latest_only: bool = Query(True, description="仅返回每个文档的最新版本"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(ProcessDocument)
    if equipment_id:
        q = q.filter(ProcessDocument.equipment_id == equipment_id)
    if category:
        q = q.filter(ProcessDocument.category == category)
    if doc_type:
        q = q.filter(ProcessDocument.doc_type == doc_type)
    if status:
        q = q.filter(ProcessDocument.status == status)
    if batch_no:
        q = q.filter(ProcessDocument.batch_no.ilike(f"%{batch_no}%"))
    if keyword:
        q = q.filter(ProcessDocument.doc_name.ilike(f"%{keyword}%"))
    if latest_only:
        q = q.filter(ProcessDocument.is_latest == True)
    return q.order_by(ProcessDocument.id.desc()).all()


# ==================== 上传 ====================

@router.post("", response_model=ProcessDocumentOut, dependencies=[Depends(require_permission("process_doc.write"))])
async def upload_process_document(
    equipment_id: int = Form(...),
    file: UploadFile = File(...),
    category: str = Form("guide", description="大类: guide指导性/record作业记录"),
    doc_name: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    batch_no: Optional[str] = Form(None),
    shift: Optional[str] = Form(None),
    production_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """上传新工艺文件（新建 group，version_seq=1，status=草稿）。

    - category=guide：指导性文件，重版本管理
    - category=record：作业记录文件，重批号/班次/生产日期
    """
    if category not in ("guide", "record"):
        raise HTTPException(status_code=400, detail="category 取值: guide/record")
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="设备不存在")
    stored_name, size, ftype, _ = _save_upload(file)
    eff_dt = _parse_date(effective_date)
    prod_dt = _parse_date(production_date)
    obj = ProcessDocument(
        equipment_id=equipment_id,
        category=category,
        doc_name=doc_name or file.filename,
        doc_type=doc_type,
        version=version,
        version_seq=1,
        group_id=uuid.uuid4().hex,
        is_latest=True,
        status="草稿",
        effective_date=eff_dt,
        batch_no=batch_no,
        shift=shift,
        production_date=prod_dt,
        stored_path=stored_name,
        file_size=size,
        file_type=ftype,
        description=description,
        uploaded_by=current_user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ==================== 元数据编辑 ====================

@router.put("/{doc_id}", response_model=ProcessDocumentOut, dependencies=[Depends(require_permission("process_doc.write"))])
def update_process_document(
    doc_id: int,
    payload: ProcessDocumentUpdate,
    db: Session = Depends(get_db),
):
    obj = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    # 仅允许修改元数据（不含 status）
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


# ==================== 删除 ====================

@router.delete("/{doc_id}", dependencies=[Depends(require_permission("process_doc.delete"))])
def delete_process_document(doc_id: int, db: Session = Depends(get_db)):
    """删除单条记录（不联动其他版本）。

    若删除的是最新版本，自动将同 group 中次新版本提升为最新。
    """
    obj = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    _delete_stored(obj.stored_path)
    group_id = obj.group_id
    was_latest = obj.is_latest
    db.delete(obj)
    db.flush()
    # 若删除的是最新版，提升次新版
    if was_latest and group_id:
        siblings = (
            db.query(ProcessDocument)
            .filter(ProcessDocument.group_id == group_id)
            .order_by(ProcessDocument.version_seq.desc())
            .all()
        )
        if siblings:
            siblings[0].is_latest = True
    db.commit()
    return {"ok": True}


# ==================== 下载 ====================

@router.get("/{doc_id}/download", dependencies=[Depends(get_current_user)])
def download_process_document(doc_id: int, db: Session = Depends(get_db)):
    obj = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    # 结构化表单记录：无物理上传文件，自动跳转到关联 form_record 的 CSV 导出
    if not obj.stored_path and obj.form_record_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/api/v1/form-records/{obj.form_record_id}/export/csv")
    base = _ensure_upload_dir()
    fp = os.path.join(base, obj.stored_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="文件已丢失")
    # 下载文件名带版本号
    dl_name = obj.doc_name
    if obj.version:
        stem, ext = os.path.splitext(dl_name)
        if ext:
            dl_name = f"{stem}_v{obj.version_seq}{ext}"
        else:
            dl_name = f"{dl_name}_v{obj.version_seq}"
    return FileResponse(fp, filename=dl_name)


# ==================== 版本管理 ====================

@router.get("/{doc_id}/versions", response_model=list[ProcessDocumentOut])
def list_versions(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """列出某工艺文件的所有版本（同 group_id）。"""
    obj = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    return (
        db.query(ProcessDocument)
        .filter(ProcessDocument.group_id == obj.group_id)
        .order_by(ProcessDocument.version_seq.desc())
        .all()
    )


@router.post(
    "/{doc_id}/versions",
    response_model=ProcessDocumentOut,
    dependencies=[Depends(require_permission("process_doc.write"))],
)
async def create_new_version(
    doc_id: int,
    file: UploadFile = File(...),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    batch_no: Optional[str] = Form(None),
    shift: Optional[str] = Form(None),
    production_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """为现有文档上传新版本。

    - 复用原 doc_name / doc_type / category / group_id
    - version_seq 自增，新版本 is_latest=True，旧版置 False
    - 新版本状态默认"草稿"；作业记录字段支持覆盖（不传则继承源版本）
    """
    src = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    stored_name, size, ftype, _ = _save_upload(file)
    # 旧版本置为非最新
    db.query(ProcessDocument).filter(
        ProcessDocument.group_id == src.group_id,
        ProcessDocument.is_latest == True,
    ).update({ProcessDocument.is_latest: False}, synchronize_session=False)
    new_seq = (src.version_seq or 1) + 1
    obj = ProcessDocument(
        equipment_id=src.equipment_id,
        category=src.category,
        doc_name=src.doc_name,
        doc_type=src.doc_type,
        version=version or f"V{new_seq}",
        version_seq=new_seq,
        group_id=src.group_id,
        is_latest=True,
        status="草稿",
        effective_date=_parse_date(effective_date),
        batch_no=batch_no or src.batch_no,
        shift=shift or src.shift,
        production_date=_parse_date(production_date) or src.production_date,
        stored_path=stored_name,
        file_size=size,
        file_type=ftype,
        description=description or src.description,
        uploaded_by=current_user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ==================== 状态管理 ====================

@router.patch(
    "/{doc_id}/status",
    response_model=ProcessDocumentOut,
    dependencies=[Depends(require_permission("process_doc.write"))],
)
def transition_status(
    doc_id: int,
    payload: ProcessDocumentStatusTransition,
    db: Session = Depends(get_db),
):
    """状态流转：草稿→生效、草稿→作废、生效→作废。

    - 草稿→生效：必须有 effective_date；同 group 旧生效版自动作废
    - 生效→作废 / 草稿→作废：可选 remark 写入 description
    """
    obj = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    _validate_transition(obj.status, payload.status)
    if payload.status == "生效":
        if not payload.effective_date:
            # 默认当前时间
            eff_dt = datetime.utcnow()
        else:
            eff_dt = payload.effective_date
        obj.status = "生效"
        obj.effective_date = eff_dt
        # 同 group 旧生效版自动作废
        db.query(ProcessDocument).filter(
            ProcessDocument.group_id == obj.group_id,
            ProcessDocument.id != obj.id,
            ProcessDocument.status == "生效",
        ).update({ProcessDocument.status: "作废"}, synchronize_session=False)
    else:  # 作废
        obj.status = "作废"
        if payload.remark:
            prev = obj.description or ""
            obj.description = f"{prev}\n[作废备注] {payload.remark}".strip()
    db.commit()
    db.refresh(obj)
    return obj


# ==================== 文件替换 ====================

@router.put(
    "/{doc_id}/file",
    response_model=ProcessDocumentOut,
    dependencies=[Depends(require_permission("process_doc.write"))],
)
async def replace_file(
    doc_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """替换文件内容（保留元数据，更新文件大小/类型/上传人）。

    注意：此操作不创建新版本。如需保留旧文件，请使用"上传新版本"。
    """
    obj = db.query(ProcessDocument).filter(ProcessDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="工艺文件不存在")
    old_path = obj.stored_path
    stored_name, size, ftype, _ = _save_upload(file)
    obj.stored_path = stored_name
    obj.file_size = size
    obj.file_type = ftype
    obj.uploaded_by = current_user.id
    db.commit()
    db.refresh(obj)
    # 删除旧文件
    _delete_stored(old_path)
    return obj


# ==================== 工具 ====================

def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # 兼容 YYYY-MM-DD 与 ISO 格式
        return datetime.fromisoformat(s.replace("Z", ""))
    except (ValueError, AttributeError):
        return None
