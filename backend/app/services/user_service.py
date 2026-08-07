from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.models import User
from app.schemas import UserCreate, UserUpdate

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def create_user(db: Session, obj_in: UserCreate) -> User:
    if get_user_by_username(db, obj_in.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    db_obj = User(
        username=obj_in.username,
        full_name=obj_in.full_name,
        hashed_password=get_password_hash(obj_in.password),
        role=obj_in.role,
        is_active=obj_in.is_active,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_user(db: Session, db_obj: User, obj_in: UserUpdate) -> User:
    data = obj_in.model_dump(exclude_unset=True)
    if "password" in data:
        data["hashed_password"] = get_password_hash(data.pop("password"))
    for k, v in data.items():
        setattr(db_obj, k, v)
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_roles(*roles):
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return user
    return _check


def init_default_admin(db: Session) -> User:
    admin = get_user_by_username(db, "admin")
    if admin:
        return admin
    return create_user(
        db,
        UserCreate(
            username="admin",
            password="admin123",
            full_name="系统管理员",
            role="admin",
        ),
    )
