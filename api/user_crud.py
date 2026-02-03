import fastapi
from models.user import UserCreate, UserUpdate, UserResponse
from api.auth import get_current_user, require_role
from controllers.user_controller import (
    create_user_controller,
    get_user_controller,
    list_users_controller,
    update_user_controller,
    delete_user_controller,
)
from util.supabse import supabase
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

router = fastapi.APIRouter()


class ApprovalRequest(BaseModel):
    notes: Optional[str] = None


class RejectionRequest(BaseModel):
    rejection_reason: str


@router.get("/users/pending-registrations", response_model=list[UserResponse], dependencies=[fastapi.Depends(require_role("Consultant", "Admin"))])
def get_pending_registrations():
    """Get all doctor registrations that need approval (pending or rejected)."""
    response = supabase.table("users").select("*").in_("account_status", ["pending", "rejected"]).order("created_at", desc=False).execute()
    return [UserResponse(**user) for user in response.data]


@router.post("/users/{user_id}/approve", dependencies=[fastapi.Depends(require_role("Consultant", "Admin"))])
def approve_user_registration(
    user_id: str,
    approval_request: ApprovalRequest,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """Approve a pending doctor registration."""
    # Fetch the user
    resp = supabase.table("users").select("*").eq("user_id", user_id).execute()
    
    if not resp.data:
        raise fastapi.HTTPException(status_code=404, detail="User not found")
    
    user = resp.data[0]
    
    # Allow approving pending or rejected accounts
    if user["account_status"] not in ["pending", "rejected"]:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Cannot approve user with status: {user['account_status']}"
        )
    
    # Update user to approved
    update_data = {
        "account_status": "approved",
        "approved_by": current_user["user_id"],
        "approved_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    update_resp = supabase.table("users").update(update_data).eq("user_id", user_id).execute()
    
    if not update_resp.data:
        raise fastapi.HTTPException(status_code=500, detail="Failed to approve user")
    
    return {
        "success": True,
        "message": "User registration approved successfully",
        "user_id": user_id,
        "user_name": user["name"],
        "approved_by": current_user["name"]
    }


@router.post("/users/{user_id}/reject", dependencies=[fastapi.Depends(require_role("Consultant", "Admin"))])
def reject_user_registration(
    user_id: str,
    rejection_request: RejectionRequest,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """Reject a pending doctor registration."""
    # Fetch the user
    resp = supabase.table("users").select("*").eq("user_id", user_id).execute()
    
    if not resp.data:
        raise fastapi.HTTPException(status_code=404, detail="User not found")
    
    user = resp.data[0]
    
    if user["account_status"] != "pending":
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"User account is already {user['account_status']}"
        )
    
    # Update user to rejected
    update_data = {
        "account_status": "rejected",
        "rejected_by": current_user["user_id"],
        "rejection_reason": rejection_request.rejection_reason,
        "rejected_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    update_resp = supabase.table("users").update(update_data).eq("user_id", user_id).execute()
    
    if not update_resp.data:
        raise fastapi.HTTPException(status_code=500, detail="Failed to reject user")
    
    return {
        "success": True,
        "message": "User registration rejected",
        "user_id": user_id,
        "user_name": user["name"],
        "rejection_reason": rejection_request.rejection_reason,
        "rejected_by": current_user["name"]
    }


@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[fastapi.Depends(get_current_user)])
def get_user(user_id: str):
    user = get_user_controller(user_id)
    return UserResponse(**user)

@router.get("/users/", dependencies=[fastapi.Depends(get_current_user)])
def list_users():
    users = list_users_controller()
    return [UserResponse(**user) for user in users]

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[fastapi.Depends(require_role("Admin"))])
def update_user(user_id: str, user: UserUpdate):
    updated_user = update_user_controller(user_id, user)
    return UserResponse(**updated_user)

@router.delete("/users/{user_id}", dependencies=[fastapi.Depends(require_role("Admin"))])
def delete_user(user_id: str):
    delete_user_controller(user_id)
    return {"detail": "User deleted successfully"}