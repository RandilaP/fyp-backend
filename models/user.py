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
    ward_id: Optional[str] = None  # Required for Doctors, optional for Consultants/Admins

# Request model for updating a user
class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[RoleEnum]
    ward_id: Optional[str] = None

# Response model
class UserResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    role: RoleEnum
    account_status: Optional[AccountStatus] = AccountStatus.APPROVED
    ward_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
