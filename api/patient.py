import fastapi
from api.auth import require_role, get_current_user
from models.patient import PatientCreate, PatientUpdate, PatientResponse
from models.bht_record import BHTRecordResponse
from models.llm_report import LLMReportCreate, LLMReportUpdate, LLMReportResponse
from util.supabse import supabase
from typing import Optional
from datetime import datetime

router = fastapi.APIRouter()

@router.post("/patients/", response_model=PatientResponse)
def create_patient(
    patient: PatientCreate,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Create a new patient. Doctors can create patients in their assigned ward."""
    # Check if user has permission (Admin or Doctor)
    user_role = current_user.get("role")
    if user_role not in ["Admin", "Doctor"]:
        raise fastapi.HTTPException(
            status_code=403,
            detail="Only Admins and Doctors can create patients"
        )
    
    data = patient.dict()
    
    # If doctor is creating patient, auto-assign to their ward
    if user_role == "Doctor":
        doctor_ward = current_user.get("ward_id")
        if not doctor_ward:
            raise fastapi.HTTPException(
                status_code=400,
                detail="Doctor must be assigned to a ward to create patients"
            )
        data["ward_id"] = doctor_ward
    
    # Convert date/datetime to ISO string for JSON serialization
    if data.get("dob"):
        data["dob"] = data["dob"].isoformat()
    if data.get("admission_date"):
        data["admission_date"] = data["admission_date"].isoformat()
    
    response = supabase.table("patients").insert(data).execute()
    return PatientResponse(**response.data[0])

@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: str):
    response = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
    return PatientResponse(**response.data[0])

@router.get("/patients/", response_model=list[PatientResponse])
def list_patients():
    response = supabase.table("patients").select("*").execute()
    return [PatientResponse(**patient) for patient in response.data]

@router.put("/patients/{patient_id}", response_model=PatientResponse)
def update_patient(patient_id: str, patient: PatientUpdate):
    data = {k: v for k, v in patient.dict().items() if v is not None}
    response = supabase.table("patients").update(data).eq("patient_id", patient_id).execute()
    return PatientResponse(**response.data[0])


@router.get("/patients/{patient_id}/bht_records", response_model=list[BHTRecordResponse], dependencies=[fastapi.Depends(get_current_user)])
def get_patient_bht_records(
    patient_id: str,
    status: Optional[str] = fastapi.Query(None, description="Filter by status: draft, finalized, rejected")
):
    """Get all BHT records for a specific patient."""
    query = supabase.table("bht_records").select("*").eq("patient_id", patient_id)
    
    if status:
        query = query.eq("status", status)
    
    response = query.order("upload_date", desc=True).execute()
    return [BHTRecordResponse(**record) for record in response.data]


@router.get("/doctors/my-patients", response_model=list[PatientResponse])
def get_my_patients(current_user: dict = fastapi.Depends(get_current_user)):
    """Get all patients in the doctor's ward."""
    user_role = current_user.get("role")
    if user_role != "Doctor":
        raise fastapi.HTTPException(
            status_code=403,
            detail="This endpoint is only for Doctors"
        )
    
    ward_id = current_user.get("ward_id")
    if not ward_id:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Doctor must be assigned to a ward"
        )
    
    response = supabase.table("patients").select("*").eq("ward_id", ward_id).execute()
    return [PatientResponse(**patient) for patient in response.data]


@router.get("/doctors/my-bhts", response_model=list[BHTRecordResponse])
def get_my_bhts(
    current_user: dict = fastapi.Depends(get_current_user),
    status: Optional[str] = fastapi.Query(None, description="Filter by status: draft, finalized, rejected")
):
    """Get all BHT records created by the logged-in doctor."""
    user_role = current_user.get("role")
    if user_role != "Doctor":
        raise fastapi.HTTPException(
            status_code=403,
            detail="This endpoint is only for Doctors"
        )
    
    doctor_id = current_user.get("user_id")
    query = supabase.table("bht_records").select("*").eq("doctor_id", doctor_id)
    
    if status:
        query = query.eq("status", status)
    
    response = query.order("upload_date", desc=True).execute()
    return [BHTRecordResponse(**record) for record in response.data]


from utils.ocr import generate_patient_summary_with_gemini

@router.post("/patients/{patient_id}/generate-summary")
def generate_patient_summary(
    patient_id: str,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Generate a comprehensive patient summary using all BHT records and save it."""
    user_role = current_user.get("role")
    if user_role not in ["Doctor", "Consultant", "Admin"]:
        raise fastapi.HTTPException(
            status_code=403,
            detail="Only Doctors, Consultants, and Admins can generate summaries"
        )
    
    # Get patient details
    patient_response = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
    if not patient_response.data:
        raise fastapi.HTTPException(status_code=404, detail="Patient not found")
    
    patient = patient_response.data[0]
    
    # Get all BHT records for this patient
    bht_response = supabase.table("bht_records").select("*").eq("patient_id", patient_id).order("upload_date", desc=False).execute()
    
    if not bht_response.data:
        raise fastapi.HTTPException(
            status_code=400,
            detail="No BHT records found for this patient"
        )
    
    # Generate summary using Gemini
    summary_text = generate_patient_summary_with_gemini(patient, bht_response.data)
    
    # Check if summary already exists for this patient
    existing = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
    
    if existing.data:
        # Update existing summary
        updated = supabase.table("llm_reports").update({
            "summary_text": summary_text,
            "updated_at": datetime.now().isoformat(),
            "status": "draft"
        }).eq("patient_id", patient_id).execute()
        
        return LLMReportResponse(**updated.data[0])
    else:
        # Create new summary
        data = {
            "patient_id": patient_id,
            "summary_text": summary_text,
            "created_by": current_user.get("user_id"),
            "status": "draft"
        }
        created = supabase.table("llm_reports").insert(data).execute()
        
        return LLMReportResponse(**created.data[0])


@router.get("/patients/{patient_id}/summary", response_model=LLMReportResponse)
def get_patient_summary(
    patient_id: str,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Get the saved summary for a patient."""
    # Verify patient exists
    patient_response = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
    if not patient_response.data:
        raise fastapi.HTTPException(status_code=404, detail="Patient not found")
    
    # Get summary
    summary_response = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
    
    if not summary_response.data:
        raise fastapi.HTTPException(
            status_code=404,
            detail="No summary found for this patient. Generate one first."
        )
    
    return LLMReportResponse(**summary_response.data[0])


@router.put("/patients/{patient_id}/summary", response_model=LLMReportResponse)
def update_patient_summary(
    patient_id: str,
    update_data: LLMReportUpdate,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Update the patient summary (edit the text)."""
    user_role = current_user.get("role")
    if user_role not in ["Doctor", "Consultant", "Admin"]:
        raise fastapi.HTTPException(
            status_code=403,
            detail="Only Doctors, Consultants, and Admins can update summaries"
        )
    
    # Check if summary exists
    existing = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
    
    if not existing.data:
        raise fastapi.HTTPException(
            status_code=404,
            detail="No summary found for this patient. Generate one first."
        )
    
    # Prepare update data
    data = {k: v for k, v in update_data.dict().items() if v is not None}
    data["updated_at"] = datetime.now().isoformat()
    
    # Update summary
    updated = supabase.table("llm_reports").update(data).eq("patient_id", patient_id).execute()
    
    return LLMReportResponse(**updated.data[0])


@router.delete("/patients/{patient_id}/summary")
def delete_patient_summary(
    patient_id: str,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Delete a patient summary (only if status is draft)."""
    user_role = current_user.get("role")
    if user_role not in ["Doctor", "Admin"]:
        raise fastapi.HTTPException(
            status_code=403,
            detail="Only Doctors and Admins can delete summaries"
        )
    
    # Check if summary exists and get its status
    existing = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
    
    if not existing.data:
        raise fastapi.HTTPException(
            status_code=404,
            detail="No summary found for this patient"
        )
    
    summary = existing.data[0]
    
    # Only allow deletion of draft summaries
    if summary.get("status") != "draft":
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Cannot delete summary with status '{summary.get('status')}'. Only draft summaries can be deleted."
        )
    
    # Delete summary
    supabase.table("llm_reports").delete().eq("patient_id", patient_id).execute()
    
    return {
        "message": "Summary deleted successfully",
        "patient_id": patient_id
    }


@router.post("/patients/{patient_id}/submit-for-review")
def submit_patient_for_review(
    patient_id: str,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Submit patient records and summary for consultant review."""
    try:
        user_role = current_user.get("role")
        if user_role != "Doctor":
            raise fastapi.HTTPException(
                status_code=403,
                detail="Only Doctors can submit patients for review"
            )
        
        # Verify patient exists and is in doctor's ward
        patient_response = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
        if not patient_response.data:
            raise fastapi.HTTPException(status_code=404, detail="Patient not found")
        
        patient = patient_response.data[0]
        doctor_ward = current_user.get("ward_id")
        
        if patient["ward_id"] != doctor_ward:
            raise fastapi.HTTPException(
                status_code=403,
                detail="You can only submit patients from your assigned ward"
            )
        
        # Get all BHT records for validation
        bht_response = supabase.table("bht_records").select("*").eq("patient_id", patient_id).execute()
        
        if not bht_response.data:
            raise fastapi.HTTPException(
                status_code=400,
                detail="Cannot submit patient with no BHT records"
            )
        
        # Check if summary exists
        summary_response = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
        
        if not summary_response.data:
            raise fastapi.HTTPException(
                status_code=400,
                detail="Cannot submit patient without a summary. Please generate and save a summary first."
            )
        
        # Update all draft BHT records to 'finalized' status with required timestamps
        draft_bhts = [bht for bht in bht_response.data if bht.get("status") == "draft"]
        now = datetime.now().isoformat()
        
        print(f"[SUBMIT] Found {len(draft_bhts)} draft BHTs to finalize")
        
        for bht in draft_bhts:
            try:
                result = supabase.table("bht_records").update({
                    "status": "finalized",
                    "finalized_date": now,
                    "discharge_timestamp": now,
                    "updated_at": now
                }).eq("bht_id", bht["bht_id"]).execute()
                print(f"[SUBMIT] Updated BHT {bht['bht_id']} to finalized")
            except Exception as e:
                print(f"[SUBMIT ERROR] Failed to update BHT {bht['bht_id']}: {str(e)}")
                raise fastapi.HTTPException(
                    status_code=500,
                    detail=f"Failed to finalize BHT record: {str(e)}"
                )
        
        # Update summary status to 'submitted'
        try:
            summary_result = supabase.table("llm_reports").update({
                "status": "submitted",
                "updated_at": datetime.now().isoformat()
            }).eq("patient_id", patient_id).execute()
            print(f"[SUBMIT] Updated summary to submitted")
        except Exception as e:
            print(f"[SUBMIT ERROR] Failed to update summary: {str(e)}")
            raise fastapi.HTTPException(
                status_code=500,
                detail=f"Failed to update summary status: {str(e)}"
            )
        
        return {
            "patient_id": patient_id,
            "status": "submitted",
            "finalized_bhts": len(draft_bhts),
            "total_bhts": len(bht_response.data),
            "summary_submitted": True,
            "submitted_by": current_user.get("user_id"),
            "submitted_at": datetime.now().isoformat()
        }
    
    except fastapi.HTTPException:
        # Re-raise HTTP exceptions (400, 403, 404)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        print(f"[SUBMIT ERROR] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise fastapi.HTTPException(
            status_code=500,
            detail=f"Failed to submit patient for review: {str(e)}"
        )
