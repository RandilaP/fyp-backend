import fastapi
from api.auth import require_role
from models.ward import WardCreate, WardUpdate, WardResponse
from util.supabse import supabase

router = fastapi.APIRouter()

@router.post("/wards/", response_model=WardResponse, dependencies=[fastapi.Depends(require_role("Admin"))])
def create_ward(ward: WardCreate):
    data = ward.dict()
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


