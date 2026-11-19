from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.auth_deps import get_current_user, require_admin
from backend.app.database import get_db
from backend.app.models import MemberModel, ExpenseModel, UserModel
from backend.app.schemas import MemberCreate, MemberResponse, ReorderPayload

router = APIRouter(prefix="/api/members", tags=["Members"])


@router.get("", response_model=List[MemberResponse])
async def list_members(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MemberModel).order_by(MemberModel.sort_order.asc(), MemberModel.id.asc()))
    return res.scalars().all()


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
    payload: MemberCreate,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Member name cannot be empty")

    existing = await db.execute(select(MemberModel).where(MemberModel.name.ilike(clean_name)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Member '{clean_name}' already exists")

    # Get max sort order
    max_res = await db.execute(select(MemberModel.sort_order).order_by(MemberModel.sort_order.desc()).limit(1))
    max_order = max_res.scalar_one_or_none()
    next_order = (max_order + 1) if max_order is not None else 0

    member = MemberModel(name=clean_name, sort_order=next_order)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.put("/reorder", status_code=status.HTTP_200_OK)
async def reorder_members(
    payload: ReorderPayload,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MemberModel))
    by_name = {m.name: m for m in res.scalars().all()}
    for idx, name in enumerate(payload.names):
        if name in by_name:
            by_name[name].sort_order = idx
    await db.commit()
    return {"status": "success"}


@router.delete("/{name}", status_code=status.HTTP_200_OK)
async def delete_member(
    name: str,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MemberModel).where(MemberModel.name == name))
    member = res.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cascade delete their expenses
    await db.delete(member)
    expenses_res = await db.execute(select(ExpenseModel).where(ExpenseModel.payer == name))
    for exp in expenses_res.scalars().all():
        await db.delete(exp)

    await db.commit()
    return {"status": "success", "message": f"Member '{name}' and associated transactions removed"}
