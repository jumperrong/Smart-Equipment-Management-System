from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission
from app.schemas import RoutingCreate, RoutingUpdate, RoutingOut
from app.services.routing_service import (
    list_routings, get_routing, create_routing, update_routing, release_routing, delete_routing
)

router = APIRouter(prefix="/routings", tags=["工序路由"])


@router.get("", response_model=list[RoutingOut])
def list_routings_api(
    product_id: int | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    cu=Depends(get_current_user),
):
    return list_routings(db, product_id=product_id, status=status, skip=skip, limit=limit)


@router.get("/{routing_id}", response_model=RoutingOut)
def get_routing_api(routing_id: int, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return get_routing(db, routing_id)


@router.post("", response_model=RoutingOut, dependencies=[Depends(require_permission("production.routing_write"))])
def create_routing_api(obj_in: RoutingCreate, db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return create_routing(db, obj_in, cu.id, cu.username)


@router.put("/{routing_id}", response_model=RoutingOut, dependencies=[Depends(require_permission("production.routing_write"))])
def update_routing_api(routing_id: int, obj_in: RoutingUpdate, db: Session = Depends(get_db)):
    r = get_routing(db, routing_id)
    return update_routing(db, r, obj_in)


@router.delete("/{routing_id}", dependencies=[Depends(require_permission("production.routing_delete"))])
def delete_routing_api(routing_id: int, db: Session = Depends(get_db)):
    r = get_routing(db, routing_id)
    delete_routing(db, r)
    return {"detail": "已删除"}


@router.post("/{routing_id}/release", response_model=RoutingOut, dependencies=[Depends(require_permission("production.routing_write"))])
def release_routing_api(routing_id: int, db: Session = Depends(get_db)):
    r = get_routing(db, routing_id)
    return release_routing(db, r)
