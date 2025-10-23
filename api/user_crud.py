import fastapi
from models.user import UserCreate, UserUpdate, UserResponse
from util.supabse import supabase
router = fastapi.APIRouter()

@router.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate):
    data = user.dict()
    response = supabase.table("users").insert(data).execute()
    created_user = response.data[0]
    return UserResponse(**created_user)

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    response = supabase.table("users").select("*").eq("user_id", user_id).execute()
    user = response.data[0]
    return UserResponse(**user)

@router.get("/users/")
def list_users():
    response = supabase.table("users").select("*").execute()
    users = response.data
    return [UserResponse(**user) for user in users]

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, user: UserUpdate):
    data = {k: v for k, v in user.dict().items() if v is not None}
    response = supabase.table("users").update(data).eq("user_id", user_id).execute()
    updated_user = response.data[0]
    return UserResponse(**updated_user)

@router.delete("/users/{user_id}")
def delete_user(user_id: str):
    supabase.table("users").delete().eq("user_id", user_id).execute()
    return {"detail": "User deleted successfully"}