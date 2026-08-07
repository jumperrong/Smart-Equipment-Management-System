from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.schemas import Token, LoginPayload, UserCreate, UserOut, UserUpdate
from app.services import user_service
from app.models import UserRole, User
from app.services.user_service import get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["认证"])


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=3)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_service.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(subject=user.username)
    return Token(access_token=token)


@router.post("/login-json", response_model=Token)
def login_json(payload: LoginPayload, db: Session = Depends(get_db)):
    user = user_service.authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(subject=user.username)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/users", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
def create_user(obj_in: UserCreate, db: Session = Depends(get_db)):
    return user_service.create_user(db, obj_in)


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ENGINEER))])
def list_users(db: Session = Depends(get_db)):
    from app.models import User
    return db.query(User).order_by(User.id.asc()).all()


@router.put("/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
def update_user(user_id: int, obj_in: UserUpdate, db: Session = Depends(get_db)):
    from app.models import User
    db_obj = db.query(User).filter(User.id == user_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user_service.update_user(db, db_obj, obj_in)


@router.delete("/users/{user_id}", dependencies=[Depends(require_roles(UserRole.ADMIN))])
def delete_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_obj = db.query(User).filter(User.id == user_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    if db_obj.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    # 防止删除最后一个管理员
    if db_obj.role == UserRole.ADMIN:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="系统至少保留一个启用的管理员")
    db.delete(db_obj)
    db.commit()
    return {"ok": True}


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def reset_password(user_id: int, payload: ResetPasswordIn, db: Session = Depends(get_db)):
    db_obj = db.query(User).filter(User.id == user_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    db_obj.hashed_password = get_password_hash(payload.new_password)
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
