import fastapi
from models.bht_record import BHTRecordCreate, BHTRecordUpdate, BHTRecordResponse
from util.supabse import supabase
from api.auth import get_current_user
from utils.ocr import (
    extract_text_with_hybrid_pipeline,
    extract_text_with_gemini,
    get_bht_extraction_spec as get_ocr_extraction_spec,
)
from utils.text_structurer import BHTExtractedData
from typing import Optional
import io
import json
import uuid
from postgrest.exceptions import APIError

router = fastapi.APIRouter()


def _strip_unavailable_optional_columns(payload: dict, api_error: APIError) -> tuple[dict, list[str]]:
    """Remove optional hybrid fields if DB schema doesn't contain them yet."""
    optional_columns = ["raw_ocr_text", "confidence_score"]
    error_message = ""
    if isinstance(getattr(api_error, "args", None), tuple) and api_error.args:
        error_message = str(api_error.args[0])
    else:
        error_message = str(api_error)

    missing = [col for col in optional_columns if f"'{col}'" in error_message]
    if not missing:
        return payload, []

    sanitized = {k: v for k, v in payload.items() if k not in missing}
    return sanitized, missing


def _insert_bht_record_with_optional_fallback(data: dict):
    """Insert record while stripping optional fields missing in schema cache."""
    payload = dict(data)
    removed_columns: list[str] = []

    while True:
        try:
            if removed_columns:
                print(
                    "Schema cache missing optional columns; retrying insert without: "
                    + ", ".join(removed_columns)
                )
            return supabase.table("bht_records").insert(payload).execute()
        except APIError as api_err:
            sanitized_payload, newly_missing = _strip_unavailable_optional_columns(payload, api_err)
            if not newly_missing:
                raise

            # Stop if payload doesn't change to avoid an infinite retry loop.
            if sanitized_payload == payload:
                raise

            payload = sanitized_payload
            for column in newly_missing:
                if column not in removed_columns:
                    removed_columns.append(column)


@router.get("/bht_records/extraction/spec")
def get_bht_extraction_spec():
    """Return canonical prompt template and output schema for cross-model evaluation."""
    return get_ocr_extraction_spec()

@router.post("/bht_records/upload", response_model=BHTRecordResponse)
def create_bht_record(
    file: fastapi.UploadFile = fastapi.File(...),
    patient_id: str = fastapi.Query(...),
    doctor_id: str = fastapi.Query(...),
    use_hybrid_pipeline: bool = fastapi.Query(
        default=True,
        description="Use hybrid OCR + Gemini structuring pipeline (True) or legacy Gemini-only (False)"
    ),
    ocr_provider: str = fastapi.Query(
        default="gemini",
        description="Preferred OCR provider for hybrid mode: gemini, trocr, or auto",
    ),
):
    """
    Upload a BHT (Medical Record) image, extract structured data using hybrid OCR pipeline,
    and insert it into the database.
    
    **Hybrid Pipeline (Recommended - Default)**:
    - Stage 1: OCR extracts raw text (Gemini primary, TrOCR fallback)
    - Stage 2: Gemini performs semantic post-correction and structuring
    
    **Legacy Mode**:
    - Direct Gemini vision-based extraction (use_hybrid_pipeline=False)
    
    This endpoint accepts a medical record image, extracts structured medical information
    using the two-stage hybrid pipeline, and stores the complete record in the database.
    The hybrid approach provides strong extraction quality by combining
    Gemini OCR text extraction with Gemini's medical domain semantic structuring.
    """
    try:
        ocr_provider = (ocr_provider or "gemini").strip().lower()
        if ocr_provider not in {"gemini", "trocr", "auto"}:
            raise fastapi.HTTPException(
                status_code=400,
                detail="Invalid ocr_provider. Use one of: gemini, trocr, auto",
            )

        # Extract structured data using the hybrid pipeline or legacy method
        if use_hybrid_pipeline:
            extracted_data = extract_text_with_hybrid_pipeline(file, ocr_provider=ocr_provider)
        else:
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
        
        # Add hybrid pipeline metadata if available
        if extracted_data.raw_ocr_text:
            data["raw_ocr_text"] = extracted_data.raw_ocr_text
        if extracted_data.confidence_score is not None:
            data["confidence_score"] = extracted_data.confidence_score
        
        # Insert into database with graceful fallback for optional columns not yet in DB schema cache.
        resp = _insert_bht_record_with_optional_fallback(data)
        
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


@router.get("/bht_records/{record_id}/extraction-json")
def get_bht_record_extraction_json(record_id: str):
    """Return normalized extracted JSON for a BHT record exactly as stored/extracted."""
    try:
        uuid.UUID(record_id)
    except ValueError:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Invalid BHT ID format: '{record_id}'. Expected a valid UUID.",
        )

    resp = supabase.table("bht_records").select("bht_id,ocr_text").eq("bht_id", record_id).execute()

    if not resp.data:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"BHT record with ID '{record_id}' not found",
        )

    row = resp.data[0]
    raw_ocr_payload = row.get("ocr_text")

    if raw_ocr_payload is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No extracted JSON found in ocr_text for BHT ID '{record_id}'",
        )

    try:
        parsed = json.loads(raw_ocr_payload) if isinstance(raw_ocr_payload, str) else raw_ocr_payload
        normalized = BHTExtractedData.model_validate(parsed).model_dump()
    except Exception as parse_error:
        raise fastapi.HTTPException(
            status_code=500,
            detail=f"Stored ocr_text is not valid extraction JSON: {str(parse_error)}",
        )

    return {
        "bht_id": row.get("bht_id"),
        "extracted_json": normalized,
    }

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

