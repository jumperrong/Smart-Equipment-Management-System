from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
import bcrypt

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
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain_password), _to_bytes(hashed_password))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    hashed = bcrypt.hashpw(_to_bytes(password[:72]), bcrypt.gensalt(rounds=10))
    return hashed.decode("utf-8")
