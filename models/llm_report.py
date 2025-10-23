from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LLMReportCreate(BaseModel):
    bht_id: str
    summary_text: str
    approved_by_consultant_id: Optional[str]

class LLMReportResponse(BaseModel):
    report_id: str
    bht_id: str
    summary_text: str
    generated_at: datetime
    approved_by_consultant_id: Optional[str]

    class Config:
        orm_mode = True
