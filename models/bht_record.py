from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class BHTRecordCreate(BaseModel):
    patient_id: str
    doctor_id: str
    ocr_text: Optional[str]
    validated_text: Optional[str]
    diagnosis: Optional[str]
    symptoms: Optional[str]
    treatment_plan: Optional[str]
    medications: Optional[str]
    vitals: Optional[Dict]
    procedures: Optional[str]
    lab_results: Optional[Dict]
    notes: Optional[str]
    status: Optional[str] = "draft"

class BHTRecordUpdate(BaseModel):
    validated_text: Optional[str]
    diagnosis: Optional[str]
    symptoms: Optional[str]
    treatment_plan: Optional[str]
    medications: Optional[str]
    vitals: Optional[Dict]
    procedures: Optional[str]
    lab_results: Optional[Dict]
    notes: Optional[str]
    status: Optional[str]

class BHTRecordResponse(BaseModel):
    bht_id: str
    patient_id: str
    doctor_id: str
    upload_date: datetime
    ocr_text: Optional[str]
    validated_text: Optional[str]
    diagnosis: Optional[str]
    symptoms: Optional[str]
    treatment_plan: Optional[str]
    medications: Optional[str]
    vitals: Optional[Dict]
    procedures: Optional[str]
    lab_results: Optional[Dict]
    notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


