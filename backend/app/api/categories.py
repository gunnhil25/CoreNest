from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.auth_deps import get_current_user, require_admin
from backend.app.database import get_db
from backend.app.models import CategoryModel, UserModel
from backend.app.schemas import CategoryCreate, CategoryResponse, ReorderPayload

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CategoryModel).order_by(CategoryModel.sort_order.asc(), CategoryModel.id.asc()))
    return res.scalars().all()


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    existing = await db.execute(select(CategoryModel).where(CategoryModel.name.ilike(clean_name)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Category '{clean_name}' already exists")

    max_res = await db.execute(select(CategoryModel.sort_order).order_by(CategoryModel.sort_order.desc()).limit(1))
    max_order = max_res.scalar_one_or_none()
    next_order = (max_order + 1) if max_order is not None else 0

    category = CategoryModel(
        name=clean_name,
        icon=payload.icon,
        color=payload.color,
        sort_order=next_order
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put("/reorder", status_code=status.HTTP_200_OK)
async def reorder_categories(
    payload: ReorderPayload,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CategoryModel))
    by_name = {c.name: c for c in res.scalars().all()}
    for idx, name in enumerate(payload.names):
        if name in by_name:
            by_name[name].sort_order = idx
    await db.commit()
    return {"status": "success"}


@router.put("/{name}", response_model=CategoryResponse)
async def update_category(
    name: str,
    payload: CategoryCreate,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CategoryModel).where(CategoryModel.name == name))
    cat = res.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    cat.icon = payload.icon
    cat.color = payload.color
    if payload.sort_order is not None:
        cat.sort_order = payload.sort_order

    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/{name}", status_code=status.HTTP_200_OK)
async def delete_category(
    name: str,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CategoryModel).where(CategoryModel.name == name))
    cat = res.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    await db.delete(cat)
    await db.commit()
    return {"status": "success", "message": f"Category '{name}' deleted"}
