import fastapi
from api.auth import require_role
from models.patient import PatientCreate, PatientUpdate, PatientResponse
from util.supabse import supabase

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

