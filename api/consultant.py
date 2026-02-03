import fastapi
from typing import Optional, List
from pydantic import BaseModel
from util.supabse import supabase
from api.auth import get_current_user, require_role
from datetime import datetime, timedelta

router = fastapi.APIRouter()


class ConsultantDashboardStats(BaseModel):
    """Statistics for consultant dashboard."""
    total_pending_doctors: int
    total_pending_bhts: int
    total_patients_in_wards: int
    total_wards_managed: int
    recent_approvals_count: int
    recent_rejections_count: int
    wards_summary: List[dict]
    pending_bhts_by_ward: List[dict]


class ConsultantWardAssignment(BaseModel):
    """Model for assigning consultant to ward."""
    consultant_id: str


@router.get("/consultants/dashboard", response_model=ConsultantDashboardStats)
def get_consultant_dashboard(
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """
    Get comprehensive dashboard statistics for consultant.
    
    Returns:
    - Total pending doctor registrations
    - Total pending BHT records in consultant's wards
    - Total patients in consultant's wards
    - Recent approval/rejection activity
    - Ward-wise breakdown
    """
    consultant_id = current_user["user_id"]
    
    # Get wards managed by this consultant
    wards_resp = supabase.table("wards").select("*").eq("consultant_id", consultant_id).execute()
    wards = wards_resp.data
    ward_ids = [w["ward_id"] for w in wards]
    
    # Get total pending doctor registrations (all consultants can see this)
    pending_doctors_resp = supabase.table("users").select("user_id").eq("account_status", "pending").execute()
    total_pending_doctors = len(pending_doctors_resp.data)
    
    # Get patients in consultant's wards
    total_patients = 0
    pending_bhts_by_ward = []
    
    if ward_ids:
        patients_resp = supabase.table("patients").select("*").in_("ward_id", ward_ids).execute()
        patients = patients_resp.data
        total_patients = len(patients)
        patient_ids = [p["patient_id"] for p in patients]
        
        # Get pending BHT records for these patients
        if patient_ids:
            pending_bhts_resp = supabase.table("bht_records").select("*").in_("patient_id", patient_ids).eq("status", "draft").execute()
            pending_bhts = pending_bhts_resp.data
            
            # Group by ward
            for ward in wards:
                ward_patients = [p for p in patients if p["ward_id"] == ward["ward_id"]]
                ward_patient_ids = [p["patient_id"] for p in ward_patients]
                ward_pending_bhts = [b for b in pending_bhts if b["patient_id"] in ward_patient_ids]
                
                pending_bhts_by_ward.append({
                    "ward_id": ward["ward_id"],
                    "ward_name": ward["name"],
                    "pending_bhts_count": len(ward_pending_bhts),
                    "total_patients": len(ward_patients)
                })
        
        total_pending_bhts = sum(w["pending_bhts_count"] for w in pending_bhts_by_ward)
    else:
        total_pending_bhts = 0
    
    # Get recent approvals/rejections (last 7 days)
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    recent_approvals_resp = supabase.table("bht_records").select("bht_id").eq("approved_by_consultant_id", consultant_id).gte("finalized_date", seven_days_ago).execute()
    recent_approvals_count = len(recent_approvals_resp.data)
    
    recent_rejections_resp = supabase.table("bht_records").select("bht_id").eq("rejected_by_consultant_id", consultant_id).gte("rejected_date", seven_days_ago).execute()
    recent_rejections_count = len(recent_rejections_resp.data)
    
    # Wards summary
    wards_summary = []
    for ward in wards:
        ward_patients = [p for p in patients if p["ward_id"] == ward["ward_id"]] if ward_ids else []
        wards_summary.append({
            "ward_id": ward["ward_id"],
            "ward_name": ward["name"],
            "location": ward.get("location"),
            "total_patients": len(ward_patients)
        })
    
    return ConsultantDashboardStats(
        total_pending_doctors=total_pending_doctors,
        total_pending_bhts=total_pending_bhts,
        total_patients_in_wards=total_patients,
        total_wards_managed=len(wards),
        recent_approvals_count=recent_approvals_count,
        recent_rejections_count=recent_rejections_count,
        wards_summary=wards_summary,
        pending_bhts_by_ward=pending_bhts_by_ward
    )


@router.get("/consultants/{consultant_id}/wards")
def get_consultant_wards(
    consultant_id: str,
    current_user: dict = fastapi.Depends(get_current_user)
):
    """Get all wards managed by a specific consultant."""
    response = supabase.table("wards").select("*").eq("consultant_id", consultant_id).execute()
    return response.data


@router.post("/wards/{ward_id}/assign-consultant", dependencies=[fastapi.Depends(require_role("Admin", "Consultant"))])
def assign_consultant_to_ward(
    ward_id: str,
    assignment: ConsultantWardAssignment,
    current_user: dict = fastapi.Depends(require_role("Admin", "Consultant"))
):
    """Assign a consultant to a ward."""
    # Verify consultant exists and has correct role
    consultant_resp = supabase.table("users").select("*").eq("user_id", assignment.consultant_id).execute()
    
    if not consultant_resp.data:
        raise fastapi.HTTPException(status_code=404, detail="Consultant not found")
    
    consultant = consultant_resp.data[0]
    if consultant["role"] != "Consultant":
        raise fastapi.HTTPException(status_code=400, detail="User is not a consultant")
    
    # Update ward
    update_data = {
        "consultant_id": assignment.consultant_id,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    response = supabase.table("wards").update(update_data).eq("ward_id", ward_id).execute()
    
    if not response.data:
        raise fastapi.HTTPException(status_code=404, detail="Ward not found")
    
    return {
        "success": True,
        "message": "Consultant assigned to ward successfully",
        "ward_id": ward_id,
        "consultant_id": assignment.consultant_id,
        "consultant_name": consultant["name"]
    }
