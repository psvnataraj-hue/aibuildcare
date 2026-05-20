from datetime import datetime, timezone

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
    """B2 (Gemini audit): enforce auth_sessions for real revocation.

    The token must (a) carry a jti, (b) still have an unexpired row in
    ``auth_sessions``, and (c) point at an active user. A row that was
    DELETEd via /logout (or by an admin) immediately invalidates the
    token even though the JWT itself is still cryptographically valid.

    Cost: one extra SELECT per authenticated request. FastAPI's
    Depends-cache makes this a single hit per HTTP request, not per
    dependency call, which is fine at pilot scale (handful of authed
    admins).

    TODO: cache active sessions in Redis or add server-side session-TTL
    caching if request rate grows past a few qps.
    """
    try:
        payload = decode_token(token)
    except ValueError:
        return None
    email = payload.get("sub")
    jti = payload.get("jti")
    if not email or not jti:
        return None
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        session = conn.execute(
            "SELECT 1 FROM auth_sessions "
            "WHERE token_jti = ? AND expires_at > ?",
            (jti, now_iso),
        ).fetchone()
        if not session:
            return None
        row = conn.execute(
            "SELECT id, email, full_name, role, society_id "
            "FROM users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["jti"] = jti  # so /logout can find the row to delete
        return d


def logout(jti: str) -> int:
    """Revoke a token by deleting its auth_sessions row.

    Returns the number of rows affected (0 if the token was already
    revoked or never existed)."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM auth_sessions WHERE token_jti = ?", (jti,)
        )
        return cur.rowcount
