import fastapi
from models.bht_record import BHTRecordCreate, BHTRecordUpdate, BHTRecordResponse
from util.supabse import supabase
from api.auth import get_current_user
from google import genai
from utils.ocr import extract_text_with_gemini
import io

router = fastapi.APIRouter()

@router.post("/bht_records/upload", response_model=BHTRecordResponse)
def create_bht_record(patient_id: str, doctor_id: str, file: fastapi.UploadFile):
    # read file bytes
    file_bytes = file.file.read()
    # extract text using Gemini (or fallback)
    ocr_text = extract_text_with_gemini(file_bytes)
    data = {"patient_id": patient_id, "doctor_id": doctor_id, "ocr_text": ocr_text}
    resp = supabase.table("bht_records").insert(data).execute()
    created = resp.data[0]
    return BHTRecordResponse(**created)