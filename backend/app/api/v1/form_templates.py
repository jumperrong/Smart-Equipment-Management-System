"""表单模板管理 API：CRUD + 参考文件(空模板PDF/Excel/图片)上传下载。"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import FormTemplate, Equipment
from app.schemas import FormTemplateCreate, FormTemplateOut, FormTemplateUpdate
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.services.form_template_service import (
    get_template_or_404,
    normalize_field_schema,
)

router = APIRouter(prefix="/form-templates", tags=["表单模板"])

# 参考模板文件上传目录
_REF_DIR_NAME = os.path.join("data", "uploads", "form_templates")
_ALLOWED_REF_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".zip", ".rar"}
_MAX_REF_SIZE = 50 * 1024 * 1024  # 50MB


def _ensure_ref_dir() -> str:
    base = os.path.join(os.getcwd(), _REF_DIR_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def _save_ref_file(file: UploadFile) -> tuple[str, int, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext and ext not in _ALLOWED_REF_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext}，仅允许: {', '.join(sorted(_ALLOWED_REF_EXTS))}",
        )
    content = file.file.read()
    if len(content) > _MAX_REF_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大({len(content)}字节)，上限 {_MAX_REF_SIZE // 1024 // 1024} MB",
        )
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(_ensure_ref_dir(), stored_name)
    with open(stored_path, "wb") as f:
        f.write(content)
    return stored_name, len(content), file.filename


# ======================== 列表 ========================

@router.get("", response_model=list[FormTemplateOut])
def list_templates(
    category: Optional[str] = Query(None, description="record作业记录类 / guide通用表单类"),
    equipment_id: Optional[int] = Query(None, description="按适用机台过滤；含 equipment_id=NULL 的通用模板永远参与返回(当传 equipment_id 时)"),
    keyword: Optional[str] = Query(None, description="名称模糊搜索"),
    code: Optional[str] = Query(None, description="精确匹配模板编码"),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(FormTemplate)
    if category:
        q = q.filter(FormTemplate.category == category)
    if is_active is not None:
        q = q.filter(FormTemplate.is_active == is_active)
    if code:
        q = q.filter(FormTemplate.code == code)
    if keyword:
        q = q.filter(FormTemplate.name.ilike(f"%{keyword}%"))
    if equipment_id is not None:
        q = q.filter(
            (FormTemplate.equipment_id == None) |  # noqa: E711
            (FormTemplate.equipment_id == equipment_id),
        )
    rows = q.order_by(FormTemplate.updated_at.desc()).all()
    # 补 has_ref_file 展示字段
    for r in rows:
        r.has_ref_file = bool(r.ref_stored_path)
    return rows


# ======================== 创建 ========================

@router.post(
    "",
    response_model=FormTemplateOut,
    dependencies=[Depends(require_permission("form_template.manage"))],
)
def create_template(
    payload: FormTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.equipment_id is not None:
        eq = db.query(Equipment).filter(Equipment.id == payload.equipment_id).first()
        if not eq:
            raise HTTPException(status_code=404, detail=f"适用机台 id={payload.equipment_id} 不存在")
    if payload.code:
        dup = db.query(FormTemplate).filter(FormTemplate.code == payload.code).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"模板编码已存在: {payload.code}")
    fields_norm = normalize_field_schema(
        [f.model_dump() for f in payload.field_schema] if payload.field_schema else []
    )
    obj = FormTemplate(
        name=payload.name,
        code=payload.code or None,
        category=payload.category or "record",
        equipment_id=payload.equipment_id,
        description=payload.description,
        field_schema=fields_norm,
        is_active=bool(payload.is_active),
        created_by=current_user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    obj.has_ref_file = bool(obj.ref_stored_path)
    return obj


# ======================== 详情 ========================

@router.get("/{template_id}", response_model=FormTemplateOut)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    obj = get_template_or_404(db, template_id)
    obj.has_ref_file = bool(obj.ref_stored_path)
    return obj


# ======================== 更新 ========================

@router.put(
    "/{template_id}",
    response_model=FormTemplateOut,
    dependencies=[Depends(require_permission("form_template.manage"))],
)
def update_template(
    template_id: int,
    payload: FormTemplateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    obj = get_template_or_404(db, template_id)
    data = payload.model_dump(exclude_unset=True)
    if "field_schema" in data:
        fs = data.pop("field_schema")
        data["field_schema"] = normalize_field_schema(fs or [])
    if "code" in data and data["code"]:
        dup = (
            db.query(FormTemplate)
            .filter(FormTemplate.code == data["code"], FormTemplate.id != template_id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail=f"模板编码已占用: {data['code']}")
    if "equipment_id" in data and data["equipment_id"] is not None:
        eq = db.query(Equipment).filter(Equipment.id == data["equipment_id"]).first()
        if not eq:
            raise HTTPException(status_code=404, detail=f"适用机台 id={data['equipment_id']} 不存在")
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    obj.has_ref_file = bool(obj.ref_stored_path)
    return obj


# ======================== 删除 ========================

@router.delete(
    "/{template_id}",
    dependencies=[Depends(require_permission("form_template.manage"))],
)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
):
    obj = get_template_or_404(db, template_id)
    if obj.records:
        raise HTTPException(
            status_code=400,
            detail=f"该模板已生成 {len(obj.records)} 条填写记录，不允许删除。可改为 is_active=false 停用。",
        )
    if obj.ref_stored_path:
        fp = os.path.join(_ensure_ref_dir(), obj.ref_stored_path)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
    db.delete(obj)
    db.commit()
    return {"ok": True, "removed": template_id}


# ======================== 参考模板文件 ========================

@router.post(
    "/{template_id}/ref-file",
    response_model=FormTemplateOut,
    dependencies=[Depends(require_permission("form_template.manage"))],
)
async def upload_ref_file(
    template_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    obj = get_template_or_404(db, template_id)
    old_path = obj.ref_stored_path
    stored_name, size, orig_name = _save_ref_file(file)
    obj.ref_stored_path = stored_name
    obj.ref_original_name = orig_name
    obj.ref_file_size = size
    db.commit()
    db.refresh(obj)
    if old_path and old_path != stored_name:
        fp = os.path.join(_ensure_ref_dir(), old_path)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
    obj.has_ref_file = bool(obj.ref_stored_path)
    return obj


@router.get("/{template_id}/ref-file", dependencies=[Depends(get_current_user)])
def download_ref_file(
    template_id: int,
    db: Session = Depends(get_db),
):
    obj = get_template_or_404(db, template_id)
    if not obj.ref_stored_path:
        raise HTTPException(status_code=404, detail="该模板未上传参考文件")
    fp = os.path.join(_ensure_ref_dir(), obj.ref_stored_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="参考文件物理丢失")
    return FileResponse(fp, filename=obj.ref_original_name or "template_ref")
