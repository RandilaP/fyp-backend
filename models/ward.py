from pydantic import BaseModel
from typing import Optional

class WardCreate(BaseModel):
    name: str
    location: Optional[str]
    consultant_id: Optional[str]

class WardUpdate(BaseModel):
    name: Optional[str]
    location: Optional[str]
    consultant_id: Optional[str]

class WardResponse(BaseModel):
    ward_id: str
    name: str
    location: Optional[str]
    consultant_id: Optional[str]

    class Config:
        orm_mode = True
