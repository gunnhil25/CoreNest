from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth_deps import require_admin
from backend.app.database import get_db
from backend.app.models import ExpenseModel, MemberModel, SessionModel, UserModel
from backend.app.schemas import UserCreateRequest, UserResponse, UserUpdateRequest
from backend.app.security import (
    SESSION_COOKIE_NAME,
    hash_password,
    hash_token,
    validate_password,
    validate_username,
)

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all user accounts (admin only)."""
    res = await db.execute(
        select(UserModel).order_by(
            UserModel.role.asc(),
            UserModel.display_name.asc(),
            UserModel.id.asc(),
        )
    )
    return res.scalars().all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user or admin account (admin only)."""
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

    existing = await db.execute(
        select(UserModel).where(UserModel.username == clean_username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{clean_username}' already exists",
        )

    user = UserModel(
        username=clean_username,
        display_name=clean_display,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)

    if payload.add_as_member:
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

    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update display name, role, or password for a user account (admin only)."""
    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.display_name is not None:
        clean_display = payload.display_name.strip()
        if not clean_display or len(clean_display) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name must be between 1 and 100 characters.",
            )
        user.display_name = clean_display

    if payload.role is not None and payload.role != user.role:
        if user.role == "admin" and payload.role != "admin":
            admin_count_res = await db.execute(
                select(func.count(UserModel.id)).where(UserModel.role == "admin")
            )
            admin_count = admin_count_res.scalar_one() or 0
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the last remaining administrator",
                )
        user.role = payload.role

    if payload.password:
        try:
            validate_password(payload.password)
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

        user.password_hash = hash_password(payload.password)
        delete_stmt = delete(SessionModel).where(SessionModel.user_id == user.id)
        if user.id == current_user.id:
            token = request.cookies.get(SESSION_COOKIE_NAME)
            if token:
                delete_stmt = delete_stmt.where(SessionModel.token_hash != hash_token(token))
        await db.execute(delete_stmt)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user account while preserving recorded expense history (admin only)."""
    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    if user.role == "admin":
        admin_count_res = await db.execute(
            select(func.count(UserModel.id)).where(UserModel.role == "admin")
        )
        admin_count = admin_count_res.scalar_one() or 0
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last remaining administrator",
            )

    await db.execute(
        update(ExpenseModel)
        .where(ExpenseModel.created_by_user_id == user.id)
        .values(created_by_user_id=None)
    )
    await db.execute(delete(SessionModel).where(SessionModel.user_id == user.id))
    await db.delete(user)
    await db.commit()
    return {"status": "success", "message": f"User '{user.username}' deleted"}
