from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DischargeRequestCreate(BaseModel):
    bht_id: str
    requested_by_id: str

class DischargeRequestUpdate(BaseModel):
    status: str
    approved_by_id: Optional[str]
    approved_date: Optional[datetime]

class DischargeRequestResponse(BaseModel):
    request_id: str
    bht_id: str
    requested_by_id: str
    request_date: datetime
    status: str
    approved_by_id: Optional[str]
    approved_date: Optional[datetime]

    class Config:
        orm_mode = True
