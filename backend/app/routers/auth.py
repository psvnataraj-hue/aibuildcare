from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import current_user
from ..schemas import LoginRequest, TokenResponse
from ..services import rbac
from ..services.auth_service import authenticate, logout

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    token = authenticate(body.email, body.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_endpoint(user: dict = Depends(current_user)) -> None:
    """B2 (Gemini audit): revoke the bearer token used to make this
    call. After this returns 204, the same token will be rejected by
    every subsequent ``user_from_token`` lookup (auth_sessions row
    deleted)."""
    logout(user["jti"])


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    """E3h: identity + effective permissions for the calling user.

    The frontend calls this once after login (and on app boot when a
    token is already cached) so it can filter nav + hide action
    buttons by role without round-tripping per-permission. Lists
    EFFECTIVE permissions (default matrix + per-society overrides)
    so the UI matches the actual server-side gates.
    """
    perms = rbac.permissions_for(user.get("role"), user.get("society_id"))
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role"),
        "society_id": user.get("society_id"),
        "permissions": sorted(perms),
    }
