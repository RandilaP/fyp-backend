import fastapi
from models.bht_record import BHTRecordCreate, BHTRecordUpdate, BHTRecordResponse
from util.supabse import supabase
from api.auth import get_current_user
from utils.ocr import extract_text_with_gemini
from typing import Optional
import io
import json
import uuid

router = fastapi.APIRouter()

@router.post("/bht_records/upload", response_model=BHTRecordResponse)
def create_bht_record(
    file: fastapi.UploadFile = fastapi.File(...),
    patient_id: str = fastapi.Query(...),
    doctor_id: str = fastapi.Query(...)
):
    """
    Upload a BHT (Medical Record) image, extract structured data using Gemini OCR,
    and insert it into the database.
    
    This endpoint accepts a medical record image, extracts structured medical information
    using Google's Gemini AI, and stores the complete record in the database.
    """
    try:
        # Extract structured data from the uploaded image using Gemini
        extracted_data = extract_text_with_gemini(file)
        
        if not extracted_data:
            raise fastapi.HTTPException(status_code=400, detail="Failed to extract data from image")
        
        # Prepare data for database insertion
        data = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "ocr_text": json.dumps(extracted_data.model_dump(), indent=2),
            "diagnosis": extracted_data.diagnosis,
            "symptoms": extracted_data.symptoms,
            "treatment_plan": extracted_data.treatment_plan,
            "medications": extracted_data.medications,
            "vitals": extracted_data.vitals,
            "procedures": extracted_data.procedures,
            "lab_results": extracted_data.lab_results,
            "notes": extracted_data.notes,
            "status": "draft"
        }
        
        # Insert into database
        resp = supabase.table("bht_records").insert(data).execute()
        
        if not resp.data:
            raise fastapi.HTTPException(status_code=500, detail="Failed to insert BHT record into database")
        
        created_record = resp.data[0]
        return BHTRecordResponse(**created_record)
        
    except fastapi.HTTPException:
        raise
    except Exception as e:
        print(f"Error details: {str(e)}")  # Log the actual error
        import traceback
        traceback.print_exc()  # Print full traceback
        raise fastapi.HTTPException(status_code=500, detail=f"Error processing BHT image: {str(e)}")

@router.get("/bht_records/{record_id}", response_model=BHTRecordResponse)
def get_bht_record(record_id: str):
    # Validate UUID format
    try:
        uuid.UUID(record_id)
    except ValueError:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Invalid BHT ID format: '{record_id}'. Expected a valid UUID."
        )
    
    resp = supabase.table("bht_records").select("*").eq("bht_id", record_id).execute()
    
    if not resp.data or len(resp.data) == 0:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"BHT record with ID '{record_id}' not found"
        )
    
    record = resp.data[0]
    return BHTRecordResponse(**record)

@router.get("/bht_records/", response_model=list[BHTRecordResponse])
def list_bht_records(
    ward_id: Optional[str] = fastapi.Query(None, description="Filter by ward ID"),
    patient_id: Optional[str] = fastapi.Query(None, description="Filter by patient ID"),
    status: Optional[str] = fastapi.Query(None, description="Filter by status: draft, finalized, rejected"),
    consultant_id: Optional[str] = fastapi.Query(None, description="Filter by consultant ID (approved_by)")
):
    """List BHT records with optional filtering."""
    query = supabase.table("bht_records").select("*")
    
    # Filter by patient_id directly
    if patient_id:
        query = query.eq("patient_id", patient_id)
    
    # Filter by ward_id (need to join with patients table)
    if ward_id and not patient_id:
        # Get patients in the ward first
        patients_resp = supabase.table("patients").select("patient_id").eq("ward_id", ward_id).execute()
        patient_ids = [p["patient_id"] for p in patients_resp.data]
        if patient_ids:
            query = query.in_("patient_id", patient_ids)
        else:
            return []  # No patients in ward
    
    # Filter by status
    if status:
        query = query.eq("status", status)
    
    # Filter by consultant
    if consultant_id:
        query = query.eq("approved_by_consultant_id", consultant_id)
    
    resp = query.order("upload_date", desc=True).execute()
    records = resp.data
    return [BHTRecordResponse(**record) for record in records]

@router.put("/bht_records/{record_id}", response_model=BHTRecordResponse)
def update_bht_record(record_id: str, record: BHTRecordUpdate):
    # Validate UUID format
    try:
        uuid.UUID(record_id)
    except ValueError:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Invalid BHT ID format: '{record_id}'. Expected a valid UUID."
        )
    
    data = {k: v for k, v in record.dict().items() if v is not None}
    
    if not data:
        raise fastapi.HTTPException(
            status_code=400,
            detail="No fields provided to update"
        )
    
    # Prevent direct status changes - status should only change through specific workflows
    # - draft -> finalized: Only through submit-for-review endpoint
    # - finalized -> approved/rejected: Only through consultant approval workflow
    if "status" in data:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Cannot update BHT status directly. Use the submit-for-review endpoint to finalize BHT records."
        )
    
    resp = supabase.table("bht_records").update(data).eq("bht_id", record_id).execute()
    
    if not resp.data or len(resp.data) == 0:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"BHT record with ID '{record_id}' not found"
        )
    
    updated = resp.data[0]
    return BHTRecordResponse(**updated)

