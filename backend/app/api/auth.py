from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth_deps import (
    clear_session_cookie,
    create_user_session,
    get_current_user,
    get_optional_user,
    set_session_cookie,
)
from backend.app.database import get_db
from backend.app.models import MemberModel, SessionModel, UserModel
from backend.app.schemas import (
    AuthStatusResponse,
    ChangePasswordRequest,
    LoginRequest,
    SetupAdminRequest,
    UserResponse,
)
from backend.app.security import (
    SESSION_COOKIE_NAME,
    hash_password,
    hash_token,
    normalize_username,
    validate_password,
    validate_username,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    user: Optional[UserModel] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Return whether an admin account has been initialized and current session status."""
    count_res = await db.execute(select(func.count(UserModel.id)))
    user_count = count_res.scalar_one() or 0
    return AuthStatusResponse(
        initialized=user_count > 0,
        authenticated=user is not None,
        user=user,
    )


@router.post("/setup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def setup_initial_admin(
    payload: SetupAdminRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create the very first admin account on a fresh CoreNest deployment."""
    count_res = await db.execute(select(func.count(UserModel.id)))
    user_count = count_res.scalar_one() or 0
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CoreNest is already initialized",
        )

    clean_display = (payload.display_name or "").strip()
    if not clean_display or len(clean_display) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Display name must be between 1 and 100 characters.",
        )

    try:
        clean_username = validate_username(payload.username)
        validate_password(payload.password)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    user = UserModel(
        username=clean_username,
        display_name=clean_display,
        password_hash=hash_password(payload.password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    existing_member = await db.execute(
        select(MemberModel).where(MemberModel.name.ilike(clean_display))
    )
    if existing_member.scalar_one_or_none() is None:
        max_res = await db.execute(
            select(MemberModel.sort_order).order_by(MemberModel.sort_order.desc()).limit(1)
        )
        max_order = max_res.scalar_one_or_none()
        next_order = (max_order + 1) if max_order is not None else 0
        db.add(MemberModel(name=clean_display, sort_order=next_order))

    token = create_user_session(db, user.id)
    await db.commit()
    await db.refresh(user)
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate an existing user and issue an HttpOnly session cookie."""
    clean_username = normalize_username(payload.username)
    res = await db.execute(
        select(UserModel).where(UserModel.username == clean_username)
    )
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_user_session(db, user.id)
    await db.commit()
    set_session_cookie(response, token)
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current session token and clear the session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        await db.execute(
            delete(SessionModel).where(SessionModel.token_hash == hash_token(token))
        )
        await db.commit()

    clear_session_cookie(response)
    return {"status": "success"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """Return the currently authenticated user profile."""
    return current_user


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Allow the signed-in user to change their own password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    try:
        validate_password(payload.new_password)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    current_user.password_hash = hash_password(payload.new_password)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    delete_stmt = delete(SessionModel).where(SessionModel.user_id == current_user.id)
    if token:
        delete_stmt = delete_stmt.where(SessionModel.token_hash != hash_token(token))
    await db.execute(delete_stmt)

    await db.commit()
    return {"status": "success", "message": "Password updated"}
