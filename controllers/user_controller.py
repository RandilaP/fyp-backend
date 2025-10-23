from typing import List
from util.supabse import supabase
from models.user import UserCreate, UserUpdate
import bcrypt



def create_user_controller(user: UserCreate) -> dict:
    data = user.dict()
    password = data.pop("password", None)
    if password is None:
        raise ValueError("password is required")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    data["password_hash"] = hashed.decode("utf-8")
    response = supabase.table("users").insert(data).execute()
    return response.data[0]


def get_user_controller(user_id: str) -> dict:
    response = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return response.data[0]


def list_users_controller() -> List[dict]:
    response = supabase.table("users").select("*").execute()
    return response.data


def update_user_controller(user_id: str, user: UserUpdate) -> dict:
    data = {k: v for k, v in user.dict().items() if v is not None}
    response = supabase.table("users").update(data).eq("user_id", user_id).execute()
    return response.data[0]


def delete_user_controller(user_id: str) -> None:
    supabase.table("users").delete().eq("user_id", user_id).execute()
