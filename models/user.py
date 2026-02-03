from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional
from datetime import datetime

class RoleEnum(str, Enum):
    DOCTOR = "Doctor"
    CONSULTANT = "Consultant"
    ADMIN = "Admin"

class AccountStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# Request model for creating a user
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: RoleEnum
    password: str

# Request model for updating a user
class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[RoleEnum]

# Response model
class UserResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    role: RoleEnum
    account_status: Optional[AccountStatus] = AccountStatus.APPROVED
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
