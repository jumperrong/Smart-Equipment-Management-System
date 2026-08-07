from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import UserRole
from app.schemas import EnvironmentLogCreate, EnvironmentLogOut
from app.services import environment_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/environment-logs", tags=["环境核查"])


@router.get("", response_model=list[EnvironmentLogOut])
def list_logs(
    area: Optional[str] = None,
    factory: Optional[str] = None,
    result: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return environment_service.list_logs(
        db, area=area, factory=factory, result=result, start=start, end=end, skip=skip, limit=limit
    )


@router.post("", response_model=EnvironmentLogOut, dependencies=[Depends(require_permission("environment.write"))])
def create_log(obj_in: EnvironmentLogCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    obj = obj_in.model_copy(update={"inspector_id": obj_in.inspector_id or current_user.id})
    return environment_service.create_log(db, obj)


@router.get("/{log_id}", response_model=EnvironmentLogOut)
def get_log(log_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    log = environment_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="环境核查记录不存在")
    return log


@router.put("/{log_id}", response_model=EnvironmentLogOut, dependencies=[Depends(require_permission("environment.write"))])
def update_log(log_id: int, obj_in: EnvironmentLogCreate, db: Session = Depends(get_db)):
    log = environment_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="环境核查记录不存在")
    return environment_service.update_log(db, log, obj_in)


@router.delete("/{log_id}", dependencies=[Depends(require_permission("environment.delete"))])
def delete_log(log_id: int, db: Session = Depends(get_db)):
    environment_service.delete_log(db, log_id)
    return {"ok": True}
