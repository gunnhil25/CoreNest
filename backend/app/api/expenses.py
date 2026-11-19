import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.auth_deps import get_current_user
from backend.app.database import get_db
from backend.app.models import ExpenseModel, UserModel
from backend.app.schemas import ExpenseCreate, ExpenseResponse

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])


@router.get("", response_model=List[ExpenseResponse])
async def list_expenses(
    category: Optional[str] = Query(None, description="Filter by category"),
    payer: Optional[str] = Query(None, description="Filter by payer"),
    sort: Optional[str] = Query("date-desc", description="Sort order"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ExpenseModel)
    if category and category != "all":
        query = query.where(ExpenseModel.category == category)
    if payer:
        query = query.where(ExpenseModel.payer == payer)

    if sort == "date-asc":
        query = query.order_by(ExpenseModel.date.asc(), ExpenseModel.id.asc())
    elif sort == "amount-desc":
        query = query.order_by(ExpenseModel.amount.desc())
    elif sort == "amount-asc":
        query = query.order_by(ExpenseModel.amount.asc())
    elif sort == "person":
        query = query.order_by(ExpenseModel.payer.asc(), ExpenseModel.date.desc())
    elif sort == "category":
        query = query.order_by(ExpenseModel.category.asc(), ExpenseModel.date.desc())
    else:  # date-desc
        query = query.order_by(ExpenseModel.date.desc(), ExpenseModel.id.desc())

    res = await db.execute(query)
    return res.scalars().all()


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exp_id = payload.id if payload.id else int(time.time() * 1000)
    while (await db.execute(select(ExpenseModel.id).where(ExpenseModel.id == exp_id))).scalar_one_or_none() is not None:
        exp_id += 1

    desc = payload.desc.strip() if payload.desc else payload.category

    expense = ExpenseModel(
        id=exp_id,
        desc=desc,
        amount=payload.amount,
        payer=payload.payer,
        category=payload.category,
        date=payload.date,
        created_by_user_id=current_user.id,
        created_by_name=current_user.display_name,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.put("/{id}", response_model=ExpenseResponse)
async def update_expense(
    id: int,
    payload: ExpenseCreate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(ExpenseModel).where(ExpenseModel.id == id))
    expense = res.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense transaction not found")

    if current_user.role != "admin" and expense.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit transactions that you recorded",
        )

    expense.desc = payload.desc.strip() if payload.desc else payload.category
    expense.amount = payload.amount
    expense.payer = payload.payer
    expense.category = payload.category
    expense.date = payload.date

    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_expense(
    id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(ExpenseModel).where(ExpenseModel.id == id))
    expense = res.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense transaction not found")

    if current_user.role != "admin" and expense.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete transactions that you recorded",
        )

    await db.delete(expense)
    await db.commit()
    return {"status": "success", "message": f"Transaction #{id} deleted"}
