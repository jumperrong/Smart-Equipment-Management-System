from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import UserRole, DictionaryCategory
from app.schemas import (
    DictionaryItemCreate, DictionaryItemUpdate, DictionaryItemOut,
)
from app.services import dictionary_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/dictionaries", tags=["系统字典"])


@router.get("/categories")
def list_categories(_=Depends(get_current_user)):
    """获取字典分类元信息"""
    return dictionary_service.categories_info()


@router.get("", response_model=list[DictionaryItemOut])
def list_items(
    category: Optional[DictionaryCategory] = None,
    active_only: bool = False,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return dictionary_service.list_items(db, category=category, active_only=active_only)


@router.post("", response_model=DictionaryItemOut, dependencies=[Depends(require_permission("dictionary.manage"))])
def create_item(obj_in: DictionaryItemCreate, db: Session = Depends(get_db)):
    return dictionary_service.create_item(db, obj_in)


@router.put("/{item_id}", response_model=DictionaryItemOut, dependencies=[Depends(require_permission("dictionary.manage"))])
def update_item(item_id: int, obj_in: DictionaryItemUpdate, db: Session = Depends(get_db)):
    item = dictionary_service.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    return dictionary_service.update_item(db, item, obj_in)


@router.delete("/{item_id}", dependencies=[Depends(require_permission("dictionary.manage"))])
def delete_item(item_id: int, db: Session = Depends(get_db)):
    dictionary_service.delete_item(db, item_id)
    return {"ok": True}
