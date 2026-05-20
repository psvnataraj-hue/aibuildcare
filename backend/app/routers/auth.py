from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import current_user
from ..schemas import LoginRequest, TokenResponse
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
