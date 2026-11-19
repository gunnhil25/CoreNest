import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.auth_deps import get_current_user, require_admin
from backend.app.database import get_db
from backend.app.models import MemberModel, CategoryModel, ExpenseModel, UserModel
from backend.app.schemas import AppDataSync, CategoryBase, ExpenseBase

router = APIRouter(prefix="/api/data", tags=["Sync"])


@router.get("", response_model=AppDataSync)
async def get_all_data(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch complete household state: members, categories, and expenses."""
    # 1. Fetch members ordered by sort_order
    members_res = await db.execute(select(MemberModel).order_by(MemberModel.sort_order.asc(), MemberModel.id.asc()))
    members = [m.name for m in members_res.scalars().all()]

    # 2. Fetch categories ordered by sort_order
    categories_res = await db.execute(select(CategoryModel).order_by(CategoryModel.sort_order.asc(), CategoryModel.id.asc()))
    categories = [
        CategoryBase(
            name=c.name,
            icon=c.icon,
            color=c.color,
            sort_order=c.sort_order
        )
        for c in categories_res.scalars().all()
    ]

    # 3. Fetch expenses
    expenses_res = await db.execute(select(ExpenseModel).order_by(ExpenseModel.date.desc(), ExpenseModel.id.desc()))
    expenses = [
        ExpenseBase(
            id=e.id,
            desc=e.desc or "",
            amount=e.amount,
            payer=e.payer,
            category=e.category,
            date=e.date,
            created_by_user_id=e.created_by_user_id,
            created_by_name=e.created_by_name,
        )
        for e in expenses_res.scalars().all()
    ]

    return AppDataSync(
        members=members,
        categories=categories,
        expenses=expenses
    )


@router.post("")
async def sync_all_data(
    payload: AppDataSync,
    current_user: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Sync and persist the complete household state atomically in PostgreSQL (admin only)."""
    try:
        # --- 1. Sync Members ---
        existing_members_res = await db.execute(select(MemberModel))
        existing_members = {m.name: m for m in existing_members_res.scalars().all()}
        incoming_member_names = [m.strip() for m in payload.members if m.strip()]

        # Remove members not in incoming payload
        for name, model in list(existing_members.items()):
            if name not in incoming_member_names:
                await db.delete(model)

        # Upsert / update order
        for idx, name in enumerate(incoming_member_names):
            if name in existing_members:
                existing_members[name].sort_order = idx
            else:
                new_member = MemberModel(name=name, sort_order=idx)
                db.add(new_member)

        # --- 2. Sync Categories ---
        existing_cat_res = await db.execute(select(CategoryModel))
        existing_cats = {c.name: c for c in existing_cat_res.scalars().all()}
        incoming_cat_names = [c.name.strip() for c in payload.categories if c.name.strip()]

        # Remove categories not in incoming payload
        for name, model in list(existing_cats.items()):
            if name not in incoming_cat_names:
                await db.delete(model)

        # Upsert / update categories
        for idx, cat_data in enumerate(payload.categories):
            clean_name = cat_data.name.strip()
            if not clean_name:
                continue
            if clean_name in existing_cats:
                cat_model = existing_cats[clean_name]
                cat_model.icon = cat_data.icon
                cat_model.color = cat_data.color
                cat_model.sort_order = idx
            else:
                new_cat = CategoryModel(
                    name=clean_name,
                    icon=cat_data.icon,
                    color=cat_data.color,
                    sort_order=idx
                )
                db.add(new_cat)

        # --- 3. Sync Expenses ---
        valid_user_ids = set((await db.execute(select(UserModel.id))).scalars().all())
        existing_expenses_res = await db.execute(select(ExpenseModel))
        existing_expenses = {e.id: e for e in existing_expenses_res.scalars().all()}
        incoming_expense_ids = set()

        for exp in payload.expenses:
            exp_id = exp.id if exp.id else int(time.time() * 1000)
            while exp_id in incoming_expense_ids:
                exp_id += 1
            incoming_expense_ids.add(exp_id)
            safe_user_id = exp.created_by_user_id if exp.created_by_user_id in valid_user_ids else None
            if exp_id in existing_expenses:
                model = existing_expenses[exp_id]
                model.desc = exp.desc
                model.amount = exp.amount
                model.payer = exp.payer
                model.category = exp.category
                model.date = exp.date
                if exp.created_by_user_id is not None:
                    model.created_by_user_id = safe_user_id
                if exp.created_by_name is not None:
                    model.created_by_name = exp.created_by_name
            else:
                new_exp = ExpenseModel(
                    id=exp_id,
                    desc=exp.desc,
                    amount=exp.amount,
                    payer=exp.payer,
                    category=exp.category,
                    date=exp.date,
                    created_by_user_id=safe_user_id,
                    created_by_name=exp.created_by_name,
                )
                db.add(new_exp)

        # Remove deleted expenses
        for exp_id, model in existing_expenses.items():
            if exp_id not in incoming_expense_ids:
                await db.delete(model)

        await db.commit()
        return {"status": "success", "message": "All data synchronized successfully."}
    except Exception as err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database synchronization failed: {str(err)}")
