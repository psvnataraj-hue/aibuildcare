import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return _pwd.verify(raw, hashed)


def create_access_token(subject: str) -> tuple[str, str, datetime]:
    s = get_settings()
    jti = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=s.jwt_expire_minutes
    )
    payload = {"sub": subject, "jti": jti, "exp": expires}
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, jti, expires


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
