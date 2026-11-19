from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import SessionModel, UserModel
from backend.app.security import SESSION_COOKIE_NAME, generate_session_token, hash_token


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the HttpOnly session cookie to the response."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
        max_age=settings.SESSION_TTL_DAYS * 86400,
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie from the client."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
    )


def create_user_session(db: AsyncSession, user_id: int) -> str:
    """Stage a new SessionModel record in db (caller commits) and return the raw token."""
    token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_TTL_DAYS)
    session_row = SessionModel(
        token_hash=hash_token(token),
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(session_row)
    return token


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[UserModel]:
    """Return the authenticated UserModel for the current session cookie, or None."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    res = await db.execute(
        select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    )
    session_row = res.scalar_one_or_none()
    if not session_row:
        return None

    expires_at = session_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        await db.delete(session_row)
        await db.commit()
        return None

    user_res = await db.execute(
        select(UserModel).where(UserModel.id == session_row.user_id)
    )
    return user_res.scalar_one_or_none()


async def get_current_user(
    user: Optional[UserModel] = Depends(get_optional_user),
) -> UserModel:
    """Require an authenticated user or raise 401."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


async def require_admin(
    user: UserModel = Depends(get_current_user),
) -> UserModel:
    """Require an administrator user or raise 403."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return user
