import fastapi
from api.auth import require_role, get_current_user
from models.ward import WardCreate, WardUpdate, WardResponse
from models.bht_record import BHTRecordResponse
from models.patient import PatientResponse
from util.supabse import supabase
from typing import Optional

router = fastapi.APIRouter()

@router.post("/wards/", response_model=WardResponse)
def create_ward(
    ward: WardCreate,
    current_user: dict = fastapi.Depends(require_role("Admin", "Consultant"))
):
    """
    Create a new ward.
    - Consultants: Automatically become in charge of the ward they create
    - Admins: Can optionally specify a consultant_id or leave it empty
    """
    data = ward.dict()
    
    # If consultant creates the ward, they become the consultant in charge
    if current_user["role"] == "Consultant":
        data["consultant_id"] = current_user["user_id"]
    # Admin can specify consultant_id or leave it None
    
    response = supabase.table("wards").insert(data).execute()
    return WardResponse(**response.data[0])

@router.get("/wards/{ward_id}", response_model=WardResponse)
def get_ward(ward_id: str):
    response = supabase.table("wards").select("*").eq("ward_id", ward_id).execute()
    return WardResponse(**response.data[0])

@router.get("/wards/", response_model=list[WardResponse])
def list_wards():
    response = supabase.table("wards").select("*").execute()
    return [WardResponse(**ward) for ward in response.data]

@router.put("/wards/{ward_id}", response_model=WardResponse)
def update_ward(ward_id: str, ward: WardUpdate):
    data = {k: v for k, v in ward.dict().items() if v is not None}
    response = supabase.table("wards").update(data).eq("ward_id", ward_id).execute()
    return WardResponse(**response.data[0])


@router.get("/wards/{ward_id}/patients", response_model=list[PatientResponse], dependencies=[fastapi.Depends(get_current_user)])
def get_ward_patients(ward_id: str):
    """Get all patients in a specific ward."""
    response = supabase.table("patients").select("*").eq("ward_id", ward_id).execute()
    return [PatientResponse(**patient) for patient in response.data]


@router.get("/wards/{ward_id}/bht_records", response_model=list[BHTRecordResponse], dependencies=[fastapi.Depends(get_current_user)])
def get_ward_bht_records(
    ward_id: str,
    status: Optional[str] = fastapi.Query(None, description="Filter by status: draft, finalized, rejected")
):
    """Get all BHT records for patients in a specific ward."""
    # First, get all patients in the ward
    patients_resp = supabase.table("patients").select("patient_id").eq("ward_id", ward_id).execute()
    patient_ids = [p["patient_id"] for p in patients_resp.data]
    
    if not patient_ids:
        return []
    
    # Then get BHT records for those patients
    query = supabase.table("bht_records").select("*").in_("patient_id", patient_ids)
    
    if status:
        query = query.eq("status", status)
    
    records_resp = query.execute()
    return [BHTRecordResponse(**record) for record in records_resp.data]


