from pydantic import BaseModel
from datetime import datetime

class NoteCreate(BaseModel):
    bht_id: str
    author_id: str
    note_text: str

class NoteResponse(BaseModel):
    note_id: str
    bht_id: str
    author_id: str
    note_text: str
    created_at: datetime

    class Config:
        orm_mode = True
