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
    
    # Approval workflow fields (FR3)
    approved_by_consultant_id: Optional[str] = None
    rejected_by_consultant_id: Optional[str] = None
    finalized_date: Optional[datetime] = None
    rejected_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    discharge_timestamp: Optional[datetime] = None
    
    # Performance analytics fields (FR6 - Objective R07)
    wer: Optional[float] = None  # Word Error Rate
    ner_f1_score: Optional[float] = None  # NER F1-Score
    
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


