from typing import Optional
from util.supabse import supabase
from utils.security import hash_password, verify_password, create_access_token



def get_user_by_email(email: str) -> Optional[dict]:
    resp = supabase.table("users").select("*").eq("email", email).limit(1).execute()
    data = resp.data
    if not data:
        return None
    return data[0]


def signup_doctor(name: str, email: str, password: str, role: str = "Doctor", ward_id: str = None) -> dict:
    if get_user_by_email(email):
        raise ValueError("User already exists")
    pwd_hash = hash_password(password)
    # Doctors need approval, Consultants are auto-approved
    account_status = "pending" if role == "Doctor" else "approved"
    data = {"name": name, "email": email, "role": role, "password_hash": pwd_hash, "account_status": account_status}
    
    # Add ward_id if provided
    if ward_id:
        data["ward_id"] = ward_id
    
    resp = supabase.table("users").insert(data).execute()
    return resp.data[0]

def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    # Check if account is approved
    if user.get("account_status") != "approved":
        return None
    return user


def login_user_and_create_token(email: str, password: str) -> str:
    user = authenticate_user(email, password)
    if not user:
        return None
    token = create_access_token(subject=user["email"], data={"user_id": user["user_id"], "role": user["role"]})
    return token


def change_password(email: str, new_password: str) -> dict:
    user = get_user_by_email(email)
    if not user:
        raise ValueError("User not found")
    pwd_hash = hash_password(new_password)
    resp = supabase.table("users").update({"password_hash": pwd_hash}).eq("email", email).execute()
    if not resp.data:
        raise ValueError("Failed to update password")
    updated = resp.data[0]
    updated.pop("password_hash", None)
    return updated
