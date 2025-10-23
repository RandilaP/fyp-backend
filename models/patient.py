from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class PatientCreate(BaseModel):
    name: str
    dob: Optional[date]
    gender: Optional[str]
    ward_id: Optional[str]
    admission_date: Optional[datetime]

class PatientUpdate(BaseModel):
    name: Optional[str]
    dob: Optional[date]
    gender: Optional[str]
    ward_id: Optional[str]
    discharge_date: Optional[datetime]

class PatientResponse(BaseModel):
    patient_id: str
    name: str
    dob: Optional[date]
    gender: Optional[str]
    ward_id: Optional[str]
    admission_date: Optional[datetime]
    discharge_date: Optional[datetime]

    class Config:
        orm_mode = True
