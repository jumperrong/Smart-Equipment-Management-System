from datetime import datetime, timedelta, timezone
from typing import Any, Union, Tuple
from jose import jwt
import bcrypt
import hashlib
import re

from app.core.config import settings


def _to_bytes(s: str | bytes) -> bytes:
    return s.encode("utf-8") if isinstance(s, str) else s


def _prehash_password(password: str | bytes) -> bytes:
    """使用 SHA-256 预哈希，消除 bcrypt 72 字节密钥截断风险。

    bcrypt 仅使用密钥的前 72 字节；超长/多字节密码会被静默截断导致熵下降。
    预哈希产生固定 32 字节二进制摘要（< 72 bytes），保证完整熵且不被截断。
    """
    raw = _to_bytes(password)
    return hashlib.sha256(raw).digest()


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
    """校验密码：优先新算法（SHA-256 预哈希 → bcrypt），失败回退旧算法保证向后兼容。

    返回 True 表示密码匹配；调用方如需透明升级旧哈希，可使用 verify_password_detailed。
    """
    matched, _ = verify_password_detailed(plain_password, hashed_password)
    return matched


def verify_password_detailed(plain_password: str, hashed_password: str) -> tuple[bool, bool]:
    """返回 (匹配成功, 是否是旧算法匹配需要升级/重哈希)。"""
    pw_bytes = _to_bytes(plain_password)
    hash_bytes = _to_bytes(hashed_password)
    # 新算法：SHA-256 预哈希（固定 32 字节 → bcrypt 完整熵）
    try:
        if bcrypt.checkpw(_prehash_password(plain_password), hash_bytes):
            return True, False
    except (ValueError, TypeError):
        pass
    # 旧算法回退：原始明文截断至 72 字节
    try:
        if bcrypt.checkpw(pw_bytes[:72], hash_bytes):
            return True, True
    except (ValueError, TypeError):
        pass
    return False, False


def needs_rehash(hashed_password: str) -> bool:
    """占位：判断哈希是否需要升级；目前以 login 回退探测为准。"""
    try:
        bcrypt.hashpw(b"dummy-test-pw", _to_bytes(hashed_password))
    except (ValueError, TypeError):
        return True
    return False


def get_password_hash(password: str) -> str:
    hashed = bcrypt.hashpw(_prehash_password(password), bcrypt.gensalt(rounds=12))
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
