from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LLMReportCreate(BaseModel):
    bht_id: Optional[str] = None
    patient_id: Optional[str] = None
    summary_text: str
    created_by: Optional[str] = None
    status: Optional[str] = "draft"
    approved_by_consultant_id: Optional[str] = None

class LLMReportUpdate(BaseModel):
    summary_text: Optional[str] = None
    status: Optional[str] = None
    approved_by_consultant_id: Optional[str] = None

class LLMReportResponse(BaseModel):
    report_id: str
    bht_id: Optional[str] = None
    patient_id: Optional[str] = None
    summary_text: str
    generated_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    status: str
    approved_by_consultant_id: Optional[str] = None

    class Config:
        orm_mode = True
