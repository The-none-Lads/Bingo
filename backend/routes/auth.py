import os
from typing import Optional

from auth.csrf import verify_csrf_token
from auth.dependencies import get_current_user, require_authenticated_user
from auth.proxy import get_client_ip
from auth.rate_limit import auth_rate_limiter
from auth.security import (
    hash_password,
    validate_password_strength,
    verify_dummy_password,
    verify_password,
)
from auth.session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session,
    revoke_all_user_sessions,
    revoke_session,
    set_session_cookie,
)
from database import get_db_session
from db_models import User, UserAuthMethod
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from models import (
    AuthStatusResponse,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    RegisterRequest,
    UserResponse,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["Authentication"])


def is_registration_allowed() -> bool:
    """Check if self-registration is enabled via environment variable (default: true)."""
    val = os.getenv("ALLOW_REGISTRATION", "true").lower()
    return val in ("true", "1", "yes", "on")


def format_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new local user",
)
async def register(
    req: RegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    # 1. Check total user count to determine if this is first-admin bootstrap
    user_count_result = await db.execute(select(func.count(User.id)))
    total_users = user_count_result.scalar_one()

    # If not bootstrap and registration is disabled, reject
    if total_users > 0 and not is_registration_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User registration is currently disabled by the server administrator.",
        )

    # 2. Check if username or email is already taken
    stmt = select(User).where(
        or_(
            func.lower(User.username) == req.username.lower().strip(),
            func.lower(User.email) == req.email.lower().strip(),
        )
    )
    existing = (await db.execute(stmt)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already registered.",
        )

    # 3. Validate password and hash with Argon2id
    try:
        validate_password_strength(req.password)
        pwd_hash = hash_password(req.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # First user registered in an empty database becomes ADMIN
    assigned_role = "ADMIN" if total_users == 0 else "USER"

    new_user = User(
        username=req.username.strip(),
        email=req.email.lower().strip(),
        role=assigned_role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()  # assign ID to new_user

    auth_method = UserAuthMethod(
        user_id=new_user.id,
        auth_provider="local",
        password_hash=pwd_hash,
    )
    db.add(auth_method)
    await db.commit()
    await db.refresh(new_user)

    # Automatically issue session on registration
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    raw_token = await create_session(db, new_user.id, client_ip, user_agent)
    set_session_cookie(response, raw_token)

    return format_user_response(new_user)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Authenticate with username/email and password",
)
async def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    client_ip = get_client_ip(request)
    identifier = req.username.strip()

    # 1. Check IP rate limit
    ip_allowed, retry_after = await auth_rate_limiter.check_ip_limit(client_ip)
    if not ip_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please retry in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Check Account rate limit / cooldown
    acc_allowed, acc_retry_after = await auth_rate_limiter.check_account_status(identifier)
    if not acc_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts for this account. Please retry in {acc_retry_after} seconds.",
            headers={"Retry-After": str(acc_retry_after)},
        )

    await auth_rate_limiter.record_ip_attempt(client_ip)

    # 3. Lookup user
    stmt = (
        select(User)
        .where(
            or_(
                func.lower(User.username) == identifier.lower(),
                func.lower(User.email) == identifier.lower(),
            )
        )
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        # User not found: run dummy verification to equalize timing
        verify_dummy_password()
        await auth_rate_limiter.record_account_failure(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # 4. Find local auth method
    auth_method = None
    for am in user.auth_methods:
        if am.auth_provider == "local" and am.password_hash:
            auth_method = am
            break

    if not auth_method or not verify_password(req.password, auth_method.password_hash):
        await auth_rate_limiter.record_account_failure(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # 5. Success: reset failed attempt counter and issue session
    await auth_rate_limiter.record_account_success(identifier)
    user_agent = request.headers.get("User-Agent")
    raw_token = await create_session(db, user.id, client_ip, user_agent)
    set_session_cookie(response, raw_token)

    return format_user_response(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout current session",
)
async def logout(
    response: Response,
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db_session),
):
    if session_cookie:
        await revoke_session(db, session_cookie)
    clear_session_cookie(response)
    return {"message": "Logged out successfully"}


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Revoke all active sessions for current user",
)
async def logout_all(
    response: Response,
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
):
    count = await revoke_all_user_sessions(db, user.id)
    clear_session_cookie(response)
    return {"message": f"Successfully revoked {count} session(s)"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get profile of current authenticated user",
)
async def get_me(
    user: User = Depends(require_authenticated_user),
):
    return format_user_response(user)


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Check current authentication status",
)
async def get_status(
    user: Optional[User] = Depends(get_current_user),
):
    if user:
        return AuthStatusResponse(authenticated=True, user=format_user_response(user))
    return AuthStatusResponse(authenticated=False, user=None)


@router.post(
    "/password",
    response_model=MessageResponse,
    summary="Update password for current user",
)
async def change_password(
    req: PasswordChangeRequest,
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Find local auth method
    auth_method = None
    for am in user.auth_methods:
        if am.auth_provider == "local":
            auth_method = am
            break

    if not auth_method or not auth_method.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No local password authentication method found for this account.",
        )

    if not verify_password(req.current_password, auth_method.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    try:
        validate_password_strength(req.new_password)
        new_hash = hash_password(req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    auth_method.password_hash = new_hash
    await db.commit()

    return {"message": "Password updated successfully."}
