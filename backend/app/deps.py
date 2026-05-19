from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .services.auth_service import user_from_token
from .services import rbac

_bearer = HTTPBearer(auto_error=False)


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    user = user_from_token(cred.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        )
    return user


def current_society(user: dict = Depends(current_user)) -> int:
    """The caller's society_id, derived server-side from the token.
    Clients never pass society_id; this is the tenant boundary."""
    sid = user.get("society_id")
    if sid is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not bound to a society",
        )
    return sid


def require(permission: str) -> Callable[[dict], dict]:
    """Dependency factory: 403 unless the caller's role grants
    `permission` (single RBAC matrix in services.rbac)."""

    def _dep(user: dict = Depends(current_user)) -> dict:
        if not rbac.has_permission(user.get("role"), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{user.get('role')}' lacks '{permission}'",
            )
        return user

    return _dep
