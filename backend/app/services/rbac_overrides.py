"""Per-society RBAC overrides on top of the default matrix.

Each (society_id, role, permission) row either grants (1) or revokes
(0) that permission for that role within that society. Absent = use
the default from services.rbac.ROLE_PERMISSIONS. The `admin` role is
the OEM superuser and is deliberately NOT overridable (no way to
accidentally lock yourself out).
"""
from datetime import datetime, timezone

from ..db import get_conn
from . import rbac


class OverrideError(Exception):
    pass


def _validate(role: str, permission: str) -> None:
    if role == "admin":
        raise OverrideError("'admin' role is not overridable")
    if role not in rbac.ROLES:
        raise OverrideError(f"unknown role: {role}")
    if permission not in rbac.ALL_PERMISSIONS:
        raise OverrideError(f"unknown permission: {permission}")


def list_overrides(society_id: int) -> list[dict]:
    """Override rows for a society (empty list = pure defaults)."""
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT role, permission, granted, updated_at "
                "FROM role_permission_overrides WHERE society_id = ? "
                "ORDER BY role, permission",
                (society_id,),
            ).fetchall()
        ]


def set_override(
    society_id: int, role: str, permission: str, granted: bool
) -> dict:
    """Upsert an override. granted=True adds the permission, False
    revokes it for this role in this society."""
    _validate(role, permission)
    now = datetime.now(timezone.utc).isoformat()
    g = 1 if granted else 0
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM role_permission_overrides "
            "WHERE society_id = ? AND role = ? AND permission = ?",
            (society_id, role, permission),
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE role_permission_overrides SET granted = ?, "
                "updated_at = ? WHERE society_id = ? AND role = ? "
                "AND permission = ?",
                (g, now, society_id, role, permission),
            )
        else:
            conn.execute(
                "INSERT INTO role_permission_overrides "
                "(society_id, role, permission, granted, updated_at) "
                "VALUES (?,?,?,?,?)",
                (society_id, role, permission, g, now),
            )
    return {
        "society_id": society_id, "role": role,
        "permission": permission, "granted": granted,
    }


def clear_override(
    society_id: int, role: str, permission: str
) -> int:
    """Revert (role, permission) in this society back to the default."""
    with get_conn() as conn:
        c = conn.execute(
            "DELETE FROM role_permission_overrides "
            "WHERE society_id = ? AND role = ? AND permission = ?",
            (society_id, role, permission),
        )
        return c.rowcount


def effective_permissions(society_id: int, role: str) -> set[str]:
    """The permission set actually in force for `role` in this society
    (default ± overrides). Useful for an admin UI."""
    if role == "admin":
        return set(rbac.ALL_PERMISSIONS)  # OEM superuser
    base = set(rbac.ROLE_PERMISSIONS.get(role, frozenset()))
    with get_conn() as conn:
        for r in conn.execute(
            "SELECT permission, granted FROM role_permission_overrides "
            "WHERE society_id = ? AND role = ?",
            (society_id, role),
        ).fetchall():
            d = dict(r)
            if d["granted"]:
                base.add(d["permission"])
            else:
                base.discard(d["permission"])
    return base
