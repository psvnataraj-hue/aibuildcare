"""Role-based access control — single source of truth.

The permission matrix is the spec's Part 1.2. Every protected endpoint
declares the permission it needs (Foundation F3); no ad-hoc per-endpoint
role checks. `admin` is the pilot superuser (the seeded operator) and
implicitly holds every permission within its society.
"""
from __future__ import annotations

# --- permissions (matrix columns) ------------------------------------
FILE_COMPLAINT = "file_complaint"
VIEW_OWN = "view_own"
VIEW_ALL = "view_all"
ASSIGN = "assign"
RESOLVE = "resolve"
ESCALATE = "escalate"
AUTHORIZE_ENFORCEMENT = "authorize_enforcement"  # fines / clamping
MODIFY_STAFF = "modify_staff"                    # staff & contractors
MODIFY_CONFIG = "modify_config"                  # society config
APPROVE_REPORTS = "approve_reports"
VIEW_FINANCIAL = "view_financial"

ALL_PERMISSIONS: frozenset[str] = frozenset({
    FILE_COMPLAINT, VIEW_OWN, VIEW_ALL, ASSIGN, RESOLVE, ESCALATE,
    AUTHORIZE_ENFORCEMENT, MODIFY_STAFF, MODIFY_CONFIG, APPROVE_REPORTS,
    VIEW_FINANCIAL,
})

# --- roles (spec Part 1.1) -------------------------------------------
ROLES: frozenset[str] = frozenset({
    "resident", "staff", "contractor", "manager", "sr_manager",
    "secretary", "chairman", "committee_member", "enforcement_officer",
    "viewer", "admin",
})

_MANAGER = {
    FILE_COMPLAINT, VIEW_OWN, VIEW_ALL, ASSIGN, RESOLVE, ESCALATE,
    MODIFY_STAFF,
}
_LEADER = _MANAGER | {  # sr_manager / secretary / chairman
    AUTHORIZE_ENFORCEMENT, MODIFY_CONFIG, APPROVE_REPORTS, VIEW_FINANCIAL,
}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "resident": frozenset({FILE_COMPLAINT, VIEW_OWN}),
    "staff": frozenset({FILE_COMPLAINT, VIEW_OWN, RESOLVE}),
    "contractor": frozenset({VIEW_OWN, RESOLVE}),
    "manager": frozenset(_MANAGER),
    "sr_manager": frozenset(_LEADER),
    "secretary": frozenset(_LEADER),
    "chairman": frozenset(_LEADER),
    # committee: decide/approve but not modify staff/config (spec matrix)
    "committee_member": frozenset({
        FILE_COMPLAINT, VIEW_OWN, VIEW_ALL, ASSIGN, RESOLVE, ESCALATE,
        AUTHORIZE_ENFORCEMENT, APPROVE_REPORTS, VIEW_FINANCIAL,
    }),
    "enforcement_officer": frozenset({
        FILE_COMPLAINT, VIEW_OWN, VIEW_ALL, RESOLVE,
    }),
    "viewer": frozenset({VIEW_ALL}),  # read-only audit
    "admin": ALL_PERMISSIONS,         # pilot superuser
}


def permissions_for(
    role: str | None,
    society_id: int | None = None,
) -> frozenset[str]:
    """Effective permission set for a role within a society (E3h).

    Computed in ONE DB query (vs 11 if we looped has_permission). Used
    by /api/v1/auth/me so the frontend can hide nav + action buttons
    without round-tripping per-permission. Order:
      1. `admin` -> ALL_PERMISSIONS, no overrides applied.
      2. Base = default ROLE_PERMISSIONS[role].
      3. Apply per-society overrides (granted=1 adds, granted=0 removes).
      4. Always falls back to base on DB failure.
    """
    if role == "admin":
        return ALL_PERMISSIONS
    base = set(ROLE_PERMISSIONS.get(role or "", frozenset()))
    if society_id is None:
        return frozenset(base)
    try:
        from ..db import get_conn

        with get_conn() as conn:
            rows = [
                dict(r) for r in conn.execute(
                    "SELECT permission, granted "
                    "FROM role_permission_overrides "
                    "WHERE society_id = ? AND role = ?",
                    (society_id, role),
                ).fetchall()
            ]
        for r in rows:
            if r["granted"]:
                base.add(r["permission"])
            else:
                base.discard(r["permission"])
    except Exception:
        pass  # resilient: fall back to default matrix
    return frozenset(base)


def has_permission(
    role: str | None,
    permission: str,
    society_id: int | None = None,
) -> bool:
    """Effective permission check.

    Resolution order:
      1. `admin` is the OEM superuser -> always granted (never overridable).
      2. If society_id given and a per-society override exists for
         (role, permission), use it.
      3. Else, fall back to the default ROLE_PERMISSIONS matrix.

    DB lookup failures are resilient: fall back to the default matrix.
    """
    if role == "admin":
        return True  # OEM superuser; deliberately not overridable
    if society_id is not None:
        try:
            from ..db import get_conn

            with get_conn() as conn:
                row = conn.execute(
                    "SELECT granted FROM role_permission_overrides "
                    "WHERE society_id = ? AND role = ? AND permission = ?",
                    (society_id, role, permission),
                ).fetchone()
                if row is not None:
                    return bool(dict(row)["granted"])
        except Exception:
            pass  # resilient: fall back to default matrix
    return permission in ROLE_PERMISSIONS.get(role or "", frozenset())
