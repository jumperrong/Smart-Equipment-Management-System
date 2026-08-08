from datetime import datetime, timedelta, timezone
from typing import Any, Union, Tuple
from jose import jwt
import bcrypt
import re

from app.core.config import settings


def _to_bytes(s: str | bytes) -> bytes:
    return s.encode("utf-8") if isinstance(s, str) else s


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta | None = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "sub": str(subject),
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any], expires_delta: timedelta | None = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "sub": str(subject),
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_token_pair(subject: Union[str, Any]) -> Tuple[str, str]:
    """同时生成 access_token + refresh_token"""
    return create_access_token(subject), create_refresh_token(subject)


def decode_token(token: str) -> dict:
    """统一解码，抛出 JWTError 交由上层处理"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain_password), _to_bytes(hashed_password))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    hashed = bcrypt.hashpw(_to_bytes(password[:72]), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


_WEAK_PASSWORDS = {
    "admin123", "12345678", "password", "password1", "qwerty123",
    "abc12345", "admin@123", "1234abcd", "login123", "welcome1",
    "11111111", "00000000", "test1234", "changeme", "master123",
}


def validate_password_strength(password: str, min_length: int = 8) -> str | None:
    """校验密码复杂度，返回错误提示或 None。
    策略：长度 ≥ N，且至少包含大小写/数字/特殊字符 中的 3 类，不命中弱密码字典。
    """
    if not password:
        return "密码不能为空"
    if len(password) < min_length:
        return f"密码至少 {min_length} 位"
    if password.lower() in _WEAK_PASSWORDS:
        return "该密码属于常见弱密码，请更换"
    cls = 0
    if re.search(r"[a-z]", password): cls += 1
    if re.search(r"[A-Z]", password): cls += 1
    if re.search(r"\d", password): cls += 1
    if re.search(r"[^A-Za-z0-9]", password): cls += 1
    if cls < 3:
        return "密码需至少包含【大小写字母/数字/特殊符号】中的 3 类"
    return None
