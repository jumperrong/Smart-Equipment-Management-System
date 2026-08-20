"""派工物料齐套 Kit Check API：CRUD + 齐套校验 + 批量备料。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import (
    MaterialKitItemCreate,
    MaterialKitItemUpdate,
    MaterialKitItemOut,
    KitCheckResult,
)
from app.services.material_kit_service import (
    list_kit_items,
    get_kit_item,
    create_kit_item,
    create_kit_items_bulk,
    update_kit_item,
    check_kit,
    mark_all_kitted,
    delete_kit_item,
)

router = APIRouter(prefix="/material-kits", tags=["物料齐套"])


@router.get(
    "",
    response_model=list[MaterialKitItemOut],
    dependencies=[Depends(require_permission("production.kit_view"))],
)
def list_kit_items_api(
    dispatch_id: int | None = Query(None),
    is_kitted: bool | None = Query(None),
    keyword: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    items = list_kit_items(
        db,
        dispatch_id=dispatch_id,
        is_kitted=is_kitted,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return [MaterialKitItemOut.model_validate(x) for x in items]


@router.get(
    "/check/{dispatch_id}",
    response_model=KitCheckResult,
    dependencies=[Depends(require_permission("production.kit_view"))],
)
def check_kit_api(
    dispatch_id: int,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return check_kit(db, dispatch_id)


@router.get(
    "/{item_id}",
    response_model=MaterialKitItemOut,
    dependencies=[Depends(require_permission("production.kit_view"))],
)
def get_kit_item_api(
    item_id: int,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return MaterialKitItemOut.model_validate(get_kit_item(db, item_id))


@router.post(
    "",
    response_model=MaterialKitItemOut,
    dependencies=[Depends(require_permission("production.kit_manage"))],
)
def create_kit_item_api(
    obj_in: MaterialKitItemCreate,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return MaterialKitItemOut.model_validate(
        create_kit_item(db, obj_in, cu.id, cu.username)
    )


@router.post(
    "/bulk/{dispatch_id}",
    response_model=list[MaterialKitItemOut],
    dependencies=[Depends(require_permission("production.kit_manage"))],
)
def create_kit_items_bulk_api(
    dispatch_id: int,
    items: list[MaterialKitItemCreate],
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    created = create_kit_items_bulk(db, dispatch_id, items, cu.id, cu.username)
    return [MaterialKitItemOut.model_validate(x) for x in created]


@router.put(
    "/{item_id}",
    response_model=MaterialKitItemOut,
    dependencies=[Depends(require_permission("production.kit_manage"))],
)
def update_kit_item_api(
    item_id: int,
    obj_in: MaterialKitItemUpdate,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    item = get_kit_item(db, item_id)
    return MaterialKitItemOut.model_validate(
        update_kit_item(db, item, obj_in, cu.id, cu.username)
    )


@router.post(
    "/mark-all-kitted/{dispatch_id}",
    response_model=KitCheckResult,
    dependencies=[Depends(require_permission("production.kit_manage"))],
)
def mark_all_kitted_api(
    dispatch_id: int,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return mark_all_kitted(db, dispatch_id, cu.id, cu.username)


@router.delete(
    "/{item_id}",
    dependencies=[Depends(require_permission("production.kit_manage"))],
)
def delete_kit_item_api(
    item_id: int,
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    item = get_kit_item(db, item_id)
    delete_kit_item(db, item)
    return {"detail": "已删除"}
