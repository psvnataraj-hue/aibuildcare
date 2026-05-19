from ..db import get_conn
from ..security import (
    verify_password,
    create_access_token,
    decode_token,
)


def authenticate(email: str, password: str) -> str | None:
    """Return a JWT on success, else None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash, is_active FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if not row or not row["is_active"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        token, jti, expires = create_access_token(email)
        conn.execute(
            "INSERT INTO auth_sessions (user_id, token_jti, expires_at) "
            "VALUES (?, ?, ?)",
            (row["id"], jti, expires.isoformat()),
        )
        return token


def user_from_token(token: str) -> dict | None:
    try:
        payload = decode_token(token)
    except ValueError:
        return None
    email = payload.get("sub")
    if not email:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, full_name, role, society_id "
            "FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return dict(row) if row else None
