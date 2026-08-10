from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, validate_password_strength, verify_password_detailed
from app.models import User
from app.schemas import UserCreate, UserUpdate

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


def is_user_locked(user: User, db: Optional[Session] = None, now: Optional[datetime] = None) -> tuple[bool, int]:
    """返回 (是否锁定, 剩余分钟数)。锁定过期时自动清零计数 + 解锁并持久化。"""
    now = now or datetime.utcnow()
    if not user.locked_until:
        return False, 0
    if user.locked_until > now:
        remain = int((user.locked_until - now).total_seconds() // 60) + 1
        return True, max(1, remain)
    # 锁定已过期：清零 + 同步到 DB（db 传空则仅内存态，下一次写操作仍会 flush）
    user.locked_until = None
    user.failed_login_count = 0
    if db is not None:
        db.add(user)
        db.commit()
    return False, 0


def record_failed_login(db: Session, user: User) -> tuple[bool, int]:
    """记录失败次数，达到阈值则锁定账户。返回 (是否锁定, 剩余分钟数)。"""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    db.add(user)
    db.commit()
    if user.failed_login_count >= settings.LOGIN_FAILURE_LOCK_THRESHOLD:
        user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOGIN_FAILURE_LOCK_MINUTES)
        db.add(user)
        db.commit()
        return True, settings.LOGIN_FAILURE_LOCK_MINUTES
    return False, 0


def clear_failed_login(db: Session, user: User) -> None:
    if user.failed_login_count:
        user.failed_login_count = 0
        db.add(user)
        db.commit()


def is_weak_password_current(user: User, plain_password: str) -> bool:
    """判断当前密码是否命中弱密码或默认密码"""
    if not plain_password:
        return False
    return validate_password_strength(plain_password, settings.PASSWORD_MIN_LENGTH) is not None


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    # 无论用户是否存在都进行一次校验，规避用户名枚举（时间一致性近似）
    try:
        verify_password(password or "", "$2b$12$" + "A" * 53)
    except Exception:
        pass
    if not user:
        return None
    locked, _ = is_user_locked(user, db=db)
    if locked:
        return None
    if not verify_password(password, user.hashed_password):
        record_failed_login(db, user)
        return None
    # 透明哈希升级：旧算法用户下次登录成功后自动迁移为新哈希（SHA-256 预哈希）
    _matched, legacy_used = verify_password_detailed(password, user.hashed_password)
    if legacy_used:
        user.hashed_password = get_password_hash(password)
        db.add(user)
        db.commit()
    if not user.is_active:
        return None
    clear_failed_login(db, user)
    return user


def create_user(db: Session, obj_in: UserCreate) -> User:
    if get_user_by_username(db, obj_in.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    err = validate_password_strength(obj_in.password, settings.PASSWORD_MIN_LENGTH)
    if err:
        raise HTTPException(status_code=400, detail=f"新建用户失败：{err}")
    # 注：validate_password_strength 已覆盖弱密码字典校验，此处仅使用调用方显式传入的 must_change_password 标记
    must_change = bool(getattr(obj_in, "must_change_password", False))
    now = datetime.utcnow()
    db_obj = User(
        username=obj_in.username,
        full_name=obj_in.full_name,
        hashed_password=get_password_hash(obj_in.password),
        role=obj_in.role,
        is_active=obj_in.is_active,
        must_change_password=must_change,
        last_password_changed_at=now,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_user(db: Session, db_obj: User, obj_in: UserUpdate) -> User:
    data = obj_in.model_dump(exclude_unset=True)
    if "password" in data:
        new_pwd = data.pop("password")
        err = validate_password_strength(new_pwd, settings.PASSWORD_MIN_LENGTH)
        if err:
            raise HTTPException(status_code=400, detail=f"修改密码失败：{err}")
        data["hashed_password"] = get_password_hash(new_pwd)
        data["last_password_changed_at"] = datetime.utcnow()
        # 改密后解除 must_change_password；如果改的是弱密码则重新标记
        if validate_password_strength(new_pwd, settings.PASSWORD_MIN_LENGTH) is not None:
            data["must_change_password"] = True
        elif "must_change_password" not in data:
            data["must_change_password"] = False
        # 改密同时清空失败计数和锁定
        data["failed_login_count"] = 0
        data["locked_until"] = None
    for k, v in data.items():
        setattr(db_obj, k, v)
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    return db_obj


def change_own_password(db: Session, user: User, old_password: str, new_password: str) -> User:
    """当前用户自己修改密码（必须校验旧密码）"""
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    err = validate_password_strength(new_password, settings.PASSWORD_MIN_LENGTH)
    if err:
        raise HTTPException(status_code=400, detail=f"新密码不符合要求：{err}")
    if verify_password(new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    user.hashed_password = get_password_hash(new_password)
    user.must_change_password = False
    user.last_password_changed_at = datetime.utcnow()
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
        if payload.get("type") != "access":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_exception
    locked, _ = is_user_locked(user, db=db)
    if locked:
        raise HTTPException(status_code=401, detail="账户已被锁定，请稍后再试或联系管理员解锁")
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
        # 若仍使用默认弱密码 admin123，标记必须改密
        if verify_password("admin123", admin.hashed_password):
            if not admin.must_change_password:
                admin.must_change_password = True
                admin.last_password_changed_at = admin.last_password_changed_at or admin.created_at
                db.add(admin)
                db.commit()
        return admin
    now = datetime.utcnow()
    u = User(
        username="admin",
        full_name="系统管理员",
        role="admin",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        must_change_password=True,
        last_password_changed_at=now,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
