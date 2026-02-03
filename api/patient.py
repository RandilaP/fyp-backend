import fastapi
from api.auth import require_role, get_current_user
from models.patient import PatientCreate, PatientUpdate, PatientResponse
from models.bht_record import BHTRecordResponse
from util.supabse import supabase
from typing import Optional

router = fastapi.APIRouter()

@router.post("/patients/", response_model=PatientResponse, dependencies=[fastapi.Depends(require_role("Admin"))])
def create_patient(patient: PatientCreate):
    data = patient.dict()
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

