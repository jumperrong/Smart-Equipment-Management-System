from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_token_pair, decode_token, get_password_hash, verify_password
from app.schemas import (
    Token, TokenPair, LoginPayload, UserCreate, UserOut, UserUpdate,
    RefreshTokenIn, ChangePasswordIn,
)
from app.services import user_service
from app.models import UserRole, User
from app.services.user_service import (
    get_current_user, require_roles, is_user_locked, change_own_password,
)

router = APIRouter(prefix="/auth", tags=["认证"])


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=8)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    host = request.client.host if request.client else "unknown"
    return host or "unknown"


def _login_response(db: Session, user: User, request: Request, password_used: str | None = None):
    """登录成功：返回 token pair + must_change_password 标记。"""
    access, refresh = create_token_pair(user.username)
    # 弱密码/默认密码检测 → must_change
    must_change = bool(user.must_change_password)
    if password_used is not None and verify_password("admin123", user.hashed_password):
        must_change = True
    # 记录登录日志（简单 stdout，后续可入库做审计）
    print(f"[SEC-AUDIT] LOGIN_OK user={user.username} ip={_client_ip(request)} ua={request.headers.get('user-agent', '')[:120]}")
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        must_change_password=must_change,
    )


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db), request: Request = None):
    # OAuth2 兼容：若失败次数已超限，统一走同一套错误消息
    user = user_service.authenticate(db, form_data.username, form_data.password)
    if not user:
        db_user = user_service.get_user_by_username(db, form_data.username)
        if db_user:
            locked, remain = is_user_locked(db_user)
            if locked:
                print(f"[SEC-AUDIT] LOGIN_LOCKED user={form_data.username} ip={_client_ip(request)} remain_min={remain}")
                raise HTTPException(status_code=423, detail=f"账户已被锁定，请 {remain} 分钟后再试或联系管理员解锁")
        print(f"[SEC-AUDIT] LOGIN_FAIL user={form_data.username} ip={_client_ip(request)}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _login_response(db, user, request, password_used=form_data.password)


@router.post("/login-json", response_model=TokenPair)
def login_json(payload: LoginPayload, db: Session = Depends(get_db), request: Request = None):
    user = user_service.authenticate(db, payload.username, payload.password)
    if not user:
        db_user = user_service.get_user_by_username(db, payload.username)
        if db_user:
            locked, remain = is_user_locked(db_user)
            if locked:
                print(f"[SEC-AUDIT] LOGIN_LOCKED user={payload.username} ip={_client_ip(request)} remain_min={remain}")
                raise HTTPException(status_code=423, detail=f"账户已被锁定，请 {remain} 分钟后再试或联系管理员解锁")
        print(f"[SEC-AUDIT] LOGIN_FAIL user={payload.username} ip={_client_ip(request)}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _login_response(db, user, request, password_used=payload.password)


@router.post("/refresh", response_model=TokenPair)
def refresh_token(payload: RefreshTokenIn, db: Session = Depends(get_db), request: Request = None):
    from jose import JWTError
    try:
        data = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="令牌类型错误")
    username = data.get("sub")
    user = user_service.get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被停用")
    locked, remain = is_user_locked(user)
    if locked:
        raise HTTPException(status_code=423, detail=f"账户已被锁定，请 {remain} 分钟后再试或联系管理员解锁")
    access, refresh = create_token_pair(user.username)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        must_change_password=bool(user.must_change_password),
    )


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(payload: ChangePasswordIn, db: Session = Depends(get_db), current_user=Depends(get_current_user), request: Request = None):
    """当前用户修改自己的密码（必须提供旧密码）。"""
    change_own_password(db, current_user, payload.old_password, payload.new_password)
    print(f"[SEC-AUDIT] PASSWORD_CHANGED_OK user={current_user.username} ip={_client_ip(request)}")
    # 改密成功后使旧 token 失效 → 重新签发新的 token pair
    access, refresh = create_token_pair(current_user.username)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        must_change_password=False,
    )


@router.post("/logout")
def logout(request: Request = None, current_user=Depends(get_current_user)):
    """服务端目前不维护 token 黑名单（JWT 是无状态的）；
    客户端应在调用此接口后删除本地 token。
    记录审计日志。
    """
    print(f"[SEC-AUDIT] LOGOUT user={current_user.username} ip={_client_ip(request)}")
    return {"ok": True}


@router.post("/users", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
def create_user(obj_in: UserCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user), request: Request = None):
    u = user_service.create_user(db, obj_in)
    print(f"[SEC-AUDIT] USER_CREATE actor={current_user.username} target={u.username} role={u.role} ip={_client_ip(request)}")
    return u


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ENGINEER))])
def list_users(db: Session = Depends(get_db)):
    from app.models import User
    return db.query(User).order_by(User.id.asc()).all()


@router.put("/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
def update_user(user_id: int, obj_in: UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user), request: Request = None):
    from app.models import User
    db_obj = db.query(User).filter(User.id == user_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    u = user_service.update_user(db, db_obj, obj_in)
    print(f"[SEC-AUDIT] USER_UPDATE actor={current_user.username} target={u.username} ip={_client_ip(request)}")
    return u


@router.delete("/users/{user_id}", dependencies=[Depends(require_roles(UserRole.ADMIN))])
def delete_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user), request: Request = None):
    from app.models import User
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
    target_name = db_obj.username
    db.delete(db_obj)
    db.commit()
    print(f"[SEC-AUDIT] USER_DELETE actor={current_user.username} target={target_name} ip={_client_ip(request)}")
    return {"ok": True}


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def reset_password(user_id: int, payload: ResetPasswordIn, db: Session = Depends(get_db), current_user=Depends(get_current_user), request: Request = None):
    from app.models import User
    from app.core.security import validate_password_strength
    db_obj = db.query(User).filter(User.id == user_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    err = validate_password_strength(payload.new_password, settings.PASSWORD_MIN_LENGTH)
    if err:
        raise HTTPException(status_code=400, detail=f"重置失败：{err}")
    db_obj.hashed_password = get_password_hash(payload.new_password)
    db_obj.must_change_password = True      # 管理员重置 → 强制下次登录改密
    db_obj.last_password_changed_at = datetime.utcnow()
    db_obj.failed_login_count = 0
    db_obj.locked_until = None
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    print(f"[SEC-AUDIT] PASSWORD_RESET actor={current_user.username} target={db_obj.username} ip={_client_ip(request)}")
    return {"ok": True}


@router.post(
    "/users/{user_id}/unlock",
    response_model=UserOut,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def unlock_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user), request: Request = None):
    from app.models import User
    db_obj = db.query(User).filter(User.id == user_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    db_obj.locked_until = None
    db_obj.failed_login_count = 0
    db_obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    print(f"[SEC-AUDIT] USER_UNLOCK actor={current_user.username} target={db_obj.username} ip={_client_ip(request)}")
    return db_obj
