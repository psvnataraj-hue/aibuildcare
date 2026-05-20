"""OEM permission-override management.

Endpoints:
  GET    /api/v1/admin/permissions             — effective matrix per role
  GET    /api/v1/admin/permissions/overrides   — explicit overrides only
  PUT    /api/v1/admin/permissions/overrides   — grant/revoke a permission
  DELETE /api/v1/admin/permissions/overrides   — revert to default

Targets the caller's own society by default. The OEM (role=admin) may
pass ?society_id=N to manage any society customer; non-admin callers
are limited to their own society.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import current_user, require
from ..services import rbac, rbac_overrides

router = APIRouter(prefix="/api/v1/admin", tags=["admin-rbac"])


class OverrideBody(BaseModel):
    role: str
    permission: str
    granted: bool


def _target_society(user: dict, society_id: int | None) -> int:
    """Resolve the society to operate on. Cross-society management
    requires the OEM superuser (role=admin)."""
    own = user.get("society_id")
    if society_id is None or society_id == own:
        if own is None:
            raise HTTPException(403, "caller is not bound to a society")
        return own
    if user.get("role") != "admin":
        raise HTTPException(
            403, "cross-society management requires admin (OEM) role"
        )
    return society_id


@router.get("/permissions")
def effective_matrix(
    society_id: int | None = Query(default=None),
    user: dict = Depends(require(rbac.VIEW_ALL)),
) -> dict:
    """Effective (default + overrides) permission set for every role in
    the target society. Useful for an admin UI."""
    sid = _target_society(user, society_id)
    return {
        "society_id": sid,
        "roles": {
            role: sorted(rbac_overrides.effective_permissions(sid, role))
            for role in sorted(rbac.ROLES)
        },
    }


@router.get("/permissions/overrides")
def list_overrides(
    society_id: int | None = Query(default=None),
    user: dict = Depends(require(rbac.VIEW_ALL)),
) -> list[dict]:
    """Just the explicit overrides (empty = pure defaults)."""
    sid = _target_society(user, society_id)
    return rbac_overrides.list_overrides(sid)


@router.put("/permissions/overrides")
def upsert_override(
    body: OverrideBody,
    society_id: int | None = Query(default=None),
    user: dict = Depends(require(rbac.MODIFY_CONFIG)),
) -> dict:
    sid = _target_society(user, society_id)
    try:
        return rbac_overrides.set_override(
            sid, body.role, body.permission, body.granted
        )
    except rbac_overrides.OverrideError as e:
        raise HTTPException(400, str(e))


@router.delete("/permissions/overrides")
def delete_override(
    role: str = Query(...),
    permission: str = Query(...),
    society_id: int | None = Query(default=None),
    user: dict = Depends(require(rbac.MODIFY_CONFIG)),
) -> dict:
    sid = _target_society(user, society_id)
    n = rbac_overrides.clear_override(sid, role, permission)
    return {"cleared": n}
