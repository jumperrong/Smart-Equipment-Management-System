from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Qualification, Training, TrainingAttendee, User, Equipment, SkillLevel
from app.schemas import (
    QualificationCreate, QualificationUpdate, TrainingCreate,
)


# ============ 资质 ============

def list_qualifications(
    db: Session, user_id: Optional[int] = None, equipment_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(Qualification)
    if user_id:
        q = q.filter(Qualification.user_id == user_id)
    if equipment_id is not None:
        q = q.filter(Qualification.equipment_id == equipment_id)
    return q.order_by(Qualification.id.desc()).offset(skip).limit(limit).all()


def get_qualification(db: Session, q_id: int) -> Optional[Qualification]:
    return db.query(Qualification).filter(Qualification.id == q_id).first()


def create_qualification(db: Session, obj_in: QualificationCreate) -> Qualification:
    if not db.query(User).filter(User.id == obj_in.user_id).first():
        raise HTTPException(status_code=404, detail="用户不存在")
    if obj_in.equipment_id and not db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first():
        raise HTTPException(status_code=404, detail="设备不存在")
    obj = Qualification(**obj_in.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_qualification(db: Session, obj: Qualification, obj_in: QualificationUpdate) -> Qualification:
    data = obj_in.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_qualification(db: Session, q_id: int):
    obj = get_qualification(db, q_id)
    if not obj:
        raise HTTPException(status_code=404, detail="资质记录不存在")
    db.delete(obj)
    db.commit()


# ============ 技能矩阵 (人员 x 设备) ============

def skill_matrix(db: Session):
    """返回 {用户} x {设备} 的技能等级矩阵，供前端表格展示。"""
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).all()
    equipments = db.query(Equipment).filter(Equipment.is_active.is_(True)).order_by(Equipment.id.asc()).all()
    quals = db.query(Qualification).filter(Qualification.is_active.is_(True)).all()
    index = {}
    for q in quals:
        if q.equipment_id is None:
            continue
        index[(q.user_id, q.equipment_id)] = q.skill_level.value

    rows = []
    for u in users:
        cells = []
        for eq in equipments:
            cells.append({
                "equipment_id": eq.id,
                "equipment_name": eq.name,
                "level": index.get((u.id, eq.id), SkillLevel.NONE.value),
            })
        rows.append({
            "user_id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role.value if u.role else None,
            "cells": cells,
        })
    return {
        "equipments": [{"id": e.id, "name": e.name} for e in equipments],
        "users": rows,
    }


# ============ 培训 ============

def list_trainings(
    db: Session, equipment_id: Optional[int] = None, status: Optional[str] = None,
    skip: int = 0, limit: int = 100,
):
    q = db.query(Training)
    if equipment_id:
        q = q.filter(Training.equipment_id == equipment_id)
    if status:
        q = q.filter(Training.status == status)
    return q.order_by(Training.id.desc()).offset(skip).limit(limit).all()


def get_training(db: Session, t_id: int) -> Optional[Training]:
    return db.query(Training).filter(Training.id == t_id).first()


def create_training(db: Session, obj_in: TrainingCreate) -> Training:
    data = obj_in.model_dump()
    attendees_data = data.pop("attendees", [])
    training = Training(**data)
    db.add(training)
    db.flush()
    for a in attendees_data:
        db.add(TrainingAttendee(training_id=training.id, **a))
    db.commit()
    db.refresh(training)
    return training


def update_training_status(db: Session, training: Training, status: str) -> Training:
    training.status = status
    if status == "COMPLETED" and not training.completed_date:
        training.completed_date = datetime.utcnow()
    db.commit()
    db.refresh(training)
    return training


def add_attendee(db: Session, training: Training, user_id: int, attendance: str = "PRESENT",
                 score: Optional[float] = None, passed: bool = False, remark: Optional[str] = None) -> TrainingAttendee:
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = db.query(TrainingAttendee).filter(
        TrainingAttendee.training_id == training.id, TrainingAttendee.user_id == user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该学员已存在")
    att = TrainingAttendee(
        training_id=training.id, user_id=user_id, attendance=attendance,
        score=score, passed=passed, remark=remark,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def update_attendee(db: Session, attendee: TrainingAttendee, data: dict) -> TrainingAttendee:
    for k, v in data.items():
        setattr(attendee, k, v)
    db.commit()
    db.refresh(attendee)
    return attendee


def delete_attendee(db: Session, attendee_id: int):
    att = db.query(TrainingAttendee).filter(TrainingAttendee.id == attendee_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="培训记录不存在")
    db.delete(att)
    db.commit()


def delete_training(db: Session, t_id: int):
    t = get_training(db, t_id)
    if not t:
        raise HTTPException(status_code=404, detail="培训计划不存在")
    db.delete(t)
    db.commit()
