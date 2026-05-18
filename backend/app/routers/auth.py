from fastapi import APIRouter, HTTPException, status

from ..schemas import LoginRequest, TokenResponse
from ..services.auth_service import authenticate

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
