"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header
from uuid import UUID

from app.dependencies import (
    get_marketplace_service,
    get_credential_repository,
)
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    AuthMeResponse,
)
from app.schemas.users import UserResponse
from infrastructure.config.settings import settings
from infrastructure.security.passwords import hash_password, verify_password
from infrastructure.security.tokens import create_access_token, decode_access_token, InvalidTokenError
from infrastructure.security.credentials import DuplicateCredentialsError
from domain.users.models import UserStatus

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer_token(authorization: str | None) -> str:
    """Extract token from 'Bearer <token>' header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    return parts[1]


async def _get_current_user_id(authorization: str | None = Header(None)) -> UUID:
    """Dependency: extract and validate the current user from bearer token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    token = _extract_bearer_token(authorization)
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user_id


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    marketplace_service=Depends(get_marketplace_service),
    cred_repo=Depends(get_credential_repository),
):
    """Register a new user with credentials."""
    try:
        password_hash = hash_password(req.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Check if email already has credentials (before creating user).
    if cred_repo.get_by_email(req.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user through marketplace service.
    try:
        user = marketplace_service.create_user(req.display_name, req.email, req.phone)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Failed to create user: {e}",
        )

    # Store credentials separately with email.
    try:
        cred_repo.store(user.id, req.email, password_hash)
    except DuplicateCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Failed to store credentials: {e}",
        )

    return user


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    marketplace_service=Depends(get_marketplace_service),
    cred_repo=Depends(get_credential_repository),
):
    """Authenticate and return JWT access token."""
    # Lookup credentials by normalized email (deterministic).
    cred = cred_repo.get_by_email(req.email)
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Check password.
    if not verify_password(req.password, cred.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Get user to check status.
    try:
        user = marketplace_service.get_user(cred.user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Issue token.
    try:
        token = create_access_token(user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        )

    expires_in = settings.access_token_minutes * 60

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/me", response_model=AuthMeResponse)
def auth_me(
    user_id: UUID = Depends(_get_current_user_id),
    marketplace_service=Depends(get_marketplace_service),
):
    """Return the authenticated user info."""
    try:
        user = marketplace_service.get_user(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user
