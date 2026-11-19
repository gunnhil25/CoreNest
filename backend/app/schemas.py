from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# Category Schemas
class CategoryBase(BaseModel):
    name: str
    icon: str = "tag"
    color: str = "#75809a"
    sort_order: Optional[int] = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: Optional[int] = None

    class Config:
        from_attributes = True


# Member Schemas
class MemberBase(BaseModel):
    name: str
    sort_order: Optional[int] = 0


class MemberCreate(MemberBase):
    pass


class MemberResponse(MemberBase):
    id: Optional[int] = None

    class Config:
        from_attributes = True


# Reorder Schema
class ReorderPayload(BaseModel):
    names: List[str] = Field(default_factory=list)


# Expense Schemas
class ExpenseBase(BaseModel):
    id: Optional[int] = None
    desc: Optional[str] = ""
    amount: float
    payer: str
    category: str
    date: str
    created_by_user_id: Optional[int] = None
    created_by_name: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseResponse(ExpenseBase):
    class Config:
        from_attributes = True


# Unified Sync Payload (matches frontend /api/data format exactly)
class AppDataSync(BaseModel):
    members: List[str] = Field(default_factory=list)
    categories: List[CategoryBase] = Field(default_factory=list)
    expenses: List[ExpenseBase] = Field(default_factory=list)


# Auth & User Schemas
class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuthStatusResponse(BaseModel):
    initialized: bool
    authenticated: bool
    user: Optional[UserResponse] = None


class SetupAdminRequest(BaseModel):
    username: str
    display_name: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreateRequest(BaseModel):
    username: str
    display_name: str
    password: str
    role: Literal["admin", "user"] = "user"
    add_as_member: bool = True


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[Literal["admin", "user"]] = None
    password: Optional[str] = None


# Health check response
class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str
