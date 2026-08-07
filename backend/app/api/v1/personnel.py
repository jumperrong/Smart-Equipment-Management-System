from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import SkillLevel, UserRole
from app.schemas import (
    QualificationCreate, QualificationOut, QualificationUpdate,
    TrainingCreate, TrainingOut, TrainingAttendeeOut,
)
from app.services import personnel_service
from app.services.user_service import get_current_user
from app.services.permission_service import require_permission

router = APIRouter(prefix="/personnel", tags=["人员资质/培训/技能矩阵"])


# ============ 资质 ============

@router.get("/qualifications", response_model=list[QualificationOut])
def list_qualifications(
    user_id: Optional[int] = None, equipment_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return personnel_service.list_qualifications(db, user_id=user_id, equipment_id=equipment_id, skip=skip, limit=limit)


@router.post("/qualifications", response_model=QualificationOut, dependencies=[Depends(require_permission("personnel.qualification_write"))])
def create_qualification(obj_in: QualificationCreate, db: Session = Depends(get_db)):
    return personnel_service.create_qualification(db, obj_in)


@router.put("/qualifications/{q_id}", response_model=QualificationOut, dependencies=[Depends(require_permission("personnel.qualification_write"))])
def update_qualification(q_id: int, obj_in: QualificationUpdate, db: Session = Depends(get_db)):
    obj = personnel_service.get_qualification(db, q_id)
    if not obj:
        raise HTTPException(status_code=404, detail="资质记录不存在")
    return personnel_service.update_qualification(db, obj, obj_in)


@router.delete("/qualifications/{q_id}", dependencies=[Depends(require_permission("personnel.qualification_delete"))])
def delete_qualification(q_id: int, db: Session = Depends(get_db)):
    personnel_service.delete_qualification(db, q_id)
    return {"ok": True}


# ============ 技能矩阵 ============

@router.get("/skill-matrix")
def skill_matrix(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return personnel_service.skill_matrix(db)


# ============ 培训 ============

@router.get("/trainings", response_model=list[TrainingOut])
def list_trainings(
    equipment_id: Optional[int] = None, status: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return personnel_service.list_trainings(db, equipment_id=equipment_id, status=status, skip=skip, limit=limit)


@router.post("/trainings", response_model=TrainingOut, dependencies=[Depends(require_permission("personnel.training_write"))])
def create_training(obj_in: TrainingCreate, db: Session = Depends(get_db)):
    return personnel_service.create_training(db, obj_in)


@router.get("/trainings/{t_id}", response_model=TrainingOut)
def get_training(t_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    t = personnel_service.get_training(db, t_id)
    if not t:
        raise HTTPException(status_code=404, detail="培训计划不存在")
    return t


@router.put("/trainings/{t_id}/status", response_model=TrainingOut, dependencies=[Depends(require_permission("personnel.training_write"))])
def update_training_status(t_id: int, body: dict, db: Session = Depends(get_db)):
    t = personnel_service.get_training(db, t_id)
    if not t:
        raise HTTPException(status_code=404, detail="培训计划不存在")
    status = body.get("status")
    if status not in ("PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail="非法状态")
    return personnel_service.update_training_status(db, t, status)


@router.delete("/trainings/{t_id}", dependencies=[Depends(require_permission("personnel.training_delete"))])
def delete_training(t_id: int, db: Session = Depends(get_db)):
    personnel_service.delete_training(db, t_id)
    return {"ok": True}


class AttendeeIn(BaseModel):
    user_id: int
    attendance: str = "PRESENT"
    score: Optional[float] = None
    passed: bool = False
    remark: Optional[str] = None


class AttendeeUpdate(BaseModel):
    attendance: Optional[str] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
    remark: Optional[str] = None


@router.post("/trainings/{t_id}/attendees", response_model=TrainingAttendeeOut, dependencies=[Depends(require_permission("personnel.training_write"))])
def add_attendee(t_id: int, obj_in: AttendeeIn, db: Session = Depends(get_db)):
    t = personnel_service.get_training(db, t_id)
    if not t:
        raise HTTPException(status_code=404, detail="培训计划不存在")
    return personnel_service.add_attendee(
        db, t, obj_in.user_id, obj_in.attendance, obj_in.score, obj_in.passed, obj_in.remark
    )


@router.put("/trainings/{t_id}/attendees/{a_id}", response_model=TrainingAttendeeOut, dependencies=[Depends(require_permission("personnel.training_write"))])
def update_attendee(t_id: int, a_id: int, obj_in: AttendeeUpdate, db: Session = Depends(get_db)):
    from app.models import TrainingAttendee
    att = db.query(TrainingAttendee).filter(
        TrainingAttendee.id == a_id, TrainingAttendee.training_id == t_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="培训记录不存在")
    return personnel_service.update_attendee(db, att, obj_in.model_dump(exclude_unset=True))


@router.delete("/trainings/{t_id}/attendees/{a_id}", dependencies=[Depends(require_permission("personnel.training_delete"))])
def delete_attendee(t_id: int, a_id: int, db: Session = Depends(get_db)):
    from app.models import TrainingAttendee
    att = db.query(TrainingAttendee).filter(
        TrainingAttendee.id == a_id, TrainingAttendee.training_id == t_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="培训记录不存在")
    db.delete(att)
    db.commit()
    return {"ok": True}
