import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import EquipmentAttachment, UserRole
from app.schemas import AttachmentOut
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/equipments/{eq_id}/attachments", tags=["设备附件"])


def _ensure_upload_dir():
    base = os.path.join(os.getcwd(), "data", "uploads")
    os.makedirs(base, exist_ok=True)
    return base


@router.get("", response_model=list[AttachmentOut])
def list_attachments(eq_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(EquipmentAttachment).filter(EquipmentAttachment.equipment_id == eq_id).order_by(EquipmentAttachment.id.desc()).all()


@router.post("", response_model=AttachmentOut, dependencies=[Depends(require_permission("attachment.manage"))])
async def upload_attachment(
    eq_id: int,
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    base = _ensure_upload_dir()
    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(base, stored_name)
    content = await file.read()
    with open(stored_path, "wb") as f:
        f.write(content)
    obj = EquipmentAttachment(
        equipment_id=eq_id,
        filename=file.filename,
        stored_path=stored_name,  # 仅存文件名，拼接时再加 base
        file_size=len(content),
        file_type=file.content_type,
        category=category,
        description=description,
        uploaded_by=current_user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{att_id}", dependencies=[Depends(require_permission("attachment.manage"))])
def delete_attachment(eq_id: int, att_id: int, db: Session = Depends(get_db)):
    obj = (
        db.query(EquipmentAttachment)
        .filter(EquipmentAttachment.id == att_id, EquipmentAttachment.equipment_id == eq_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="附件不存在")
    base = _ensure_upload_dir()
    fp = os.path.join(base, obj.stored_path)
    if os.path.exists(fp):
        os.remove(fp)
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/{att_id}/download", dependencies=[Depends(get_current_user)])
def download_attachment(eq_id: int, att_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    obj = (
        db.query(EquipmentAttachment)
        .filter(EquipmentAttachment.id == att_id, EquipmentAttachment.equipment_id == eq_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="附件不存在")
    base = _ensure_upload_dir()
    fp = os.path.join(base, obj.stored_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="文件已丢失")
    return FileResponse(fp, filename=obj.filename)
