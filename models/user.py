from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional
from datetime import datetime

class RoleEnum(str, Enum):
    DOCTOR = "Doctor"
    CONSULTANT = "Consultant"
    ADMIN = "Admin"

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
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
