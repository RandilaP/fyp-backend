from pydantic import BaseModel
from datetime import datetime

class AuditLogCreate(BaseModel):
    action: str
    user_id: str
    entity: str
    entity_id: str

class AuditLogResponse(BaseModel):
    log_id: str
    action: str
    user_id: str
    entity: str
    entity_id: str
    timestamp: datetime

    class Config:
        orm_mode = True
