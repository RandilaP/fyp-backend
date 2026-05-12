import fastapi
from typing import Optional, List
from pydantic import BaseModel
from util.supabse import supabase
from api.auth import get_current_user, require_role
from datetime import datetime, timedelta
from utils.patient_visibility import filter_active_patients

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


class SubmittedPatientDetails(BaseModel):
    """Detailed view of a submitted patient for consultant review."""
    patient_id: str
    patient_name: str
    age: Optional[int]
    gender: Optional[str]
    admission_date: Optional[datetime]
    ward_id: str
    ward_name: str
    doctor_id: str
    doctor_name: str
    total_bhts: int
    finalized_bhts: int
    summary_status: str
    summary_text: Optional[str]
    summary_id: Optional[str]
    submitted_at: Optional[datetime]
    bht_records: List[dict]


class PatientReviewAction(BaseModel):
    """Action to approve or reject a patient for discharge."""
    action: str  # "approve" or "reject"
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


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
        patients = filter_active_patients(patients_resp.data)
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


@router.get("/consultants/submitted-patients")
def get_submitted_patients(
    ward_id: Optional[str] = None,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """
    Get all patients with submitted summaries in consultant's wards.
    Shows patients ready for review/discharge decision.
    
    Query params:
    - ward_id: Optional - filter by specific ward
    
    Returns list of patients with:
    - Patient details
    - Doctor who submitted
    - Summary status and text
    - Count of BHT records
    """
    consultant_id = current_user["user_id"]
    
    # Get consultant's wards
    wards_resp = supabase.table("wards").select("*").eq("consultant_id", consultant_id).execute()
    wards = wards_resp.data
    
    if not wards:
        return []
    
    ward_ids = [w["ward_id"] for w in wards]
    
    # Filter by specific ward if requested
    if ward_id:
        if ward_id not in ward_ids:
            raise fastapi.HTTPException(
                status_code=403,
                detail="You do not manage this ward"
            )
        ward_ids = [ward_id]
    
    # Get patients in these wards
    patients_resp = supabase.table("patients").select("*").in_("ward_id", ward_ids).execute()
    patients = filter_active_patients(patients_resp.data)
    
    if not patients:
        return []
    
    patient_ids = [p["patient_id"] for p in patients]
    
    # Get submitted summaries for these patients
    summaries_resp = supabase.table("llm_reports").select("*").in_("patient_id", patient_ids).eq("status", "submitted").execute()
    summaries = summaries_resp.data
    
    if not summaries:
        return []
    
    # Get all BHT records for these patients
    bhts_resp = supabase.table("bht_records").select("*").in_("patient_id", patient_ids).execute()
    all_bhts = bhts_resp.data
    
    # Get doctor and ward info
    doctor_ids = list(set([p["created_by"] for p in patients if p.get("created_by")]))
    doctors_resp = supabase.table("users").select("user_id, name, email").in_("user_id", doctor_ids).execute()
    doctors = {d["user_id"]: d for d in doctors_resp.data}
    
    wards_dict = {w["ward_id"]: w for w in wards}
    
    # Build response
    result = []
    for summary in summaries:
        patient = next((p for p in patients if p["patient_id"] == summary["patient_id"]), None)
        if not patient:
            continue
        
        patient_bhts = [b for b in all_bhts if b["patient_id"] == patient["patient_id"]]
        finalized_bhts = [b for b in patient_bhts if b["status"] == "finalized"]
        
        doctor = doctors.get(patient.get("created_by"))
        ward = wards_dict.get(patient["ward_id"])
        
        result.append({
            "patient_id": patient["patient_id"],
            "patient_name": patient["name"],
            "age": patient.get("age"),
            "gender": patient.get("gender"),
            "admission_date": patient.get("admission_date"),
            "ward_id": patient["ward_id"],
            "ward_name": ward["name"] if ward else "Unknown",
            "doctor_id": patient.get("created_by"),
            "doctor_name": doctor["name"] if doctor else "Unknown",
            "doctor_email": doctor["email"] if doctor else None,
            "total_bhts": len(patient_bhts),
            "finalized_bhts": len(finalized_bhts),
            "summary_id": summary["report_id"],
            "summary_text": summary["summary_text"],
            "summary_status": summary["status"],
            "submitted_at": summary.get("updated_at"),
            "created_at": patient.get("created_at")
        })
    
    # Sort by submission date (most recent first)
    result.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)
    
    return result


@router.get("/consultants/patients/{patient_id}/details")
def get_patient_full_details(
    patient_id: str,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """
    Get complete details of a submitted patient including all BHT records.
    For detailed review before making discharge decision.
    """
    consultant_id = current_user["user_id"]
    
    # Verify patient exists and is in consultant's ward
    patient_resp = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
    if not patient_resp.data:
        raise fastapi.HTTPException(status_code=404, detail="Patient not found")
    
    patient = patient_resp.data[0]
    
    # Check if ward is managed by this consultant
    ward_resp = supabase.table("wards").select("*").eq("ward_id", patient["ward_id"]).execute()
    if not ward_resp.data:
        raise fastapi.HTTPException(status_code=404, detail="Ward not found")
    
    ward = ward_resp.data[0]
    if ward["consultant_id"] != consultant_id:
        raise fastapi.HTTPException(
            status_code=403,
            detail="This patient is not in your ward"
        )
    
    # Get patient summary
    summary_resp = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
    summary = summary_resp.data[0] if summary_resp.data else None
    
    # Get all BHT records
    bhts_resp = supabase.table("bht_records").select("*").eq("patient_id", patient_id).order("upload_date", desc=True).execute()
    bhts = bhts_resp.data

    doctor_ids = list({bht.get("doctor_id") for bht in bhts if bht.get("doctor_id")})
    doctors_by_id = {}
    if doctor_ids:
        doctors_resp = supabase.table("users").select("user_id, name, email").in_("user_id", doctor_ids).execute()
        doctors_by_id = {doctor["user_id"]: doctor for doctor in doctors_resp.data}

    enriched_bhts = []
    for bht in bhts:
        doctor = doctors_by_id.get(bht.get("doctor_id"))
        enriched_bht = dict(bht)
        enriched_bht["doctor_name"] = doctor["name"] if doctor else None
        enriched_bht["doctor_email"] = doctor["email"] if doctor else None
        enriched_bhts.append(enriched_bht)
    
    # Get doctor info
    doctor = None
    if patient.get("created_by"):
        doctor_resp = supabase.table("users").select("user_id, name, email, role").eq("user_id", patient["created_by"]).execute()
        if doctor_resp.data:
            doctor = doctor_resp.data[0]
    
    return {
        "patient": {
            "patient_id": patient["patient_id"],
            "name": patient["name"],
            "age": patient.get("age"),
            "gender": patient.get("gender"),
            "admission_date": patient.get("admission_date"),
            "medical_history": patient.get("medical_history"),
            "allergies": patient.get("allergies"),
            "emergency_contact": patient.get("emergency_contact"),
            "created_at": patient.get("created_at")
        },
        "ward": {
            "ward_id": ward["ward_id"],
            "name": ward["name"],
            "location": ward.get("location"),
            "capacity": ward.get("capacity")
        },
        "doctor": doctor,
        "summary": {
            "report_id": summary["report_id"] if summary else None,
            "summary_text": summary["summary_text"] if summary else None,
            "status": summary["status"] if summary else None,
            "created_at": summary.get("created_at") if summary else None,
            "updated_at": summary.get("updated_at") if summary else None
        } if summary else None,
        "bht_records": enriched_bhts,
        "statistics": {
            "total_bhts": len(enriched_bhts),
            "draft_bhts": len([b for b in enriched_bhts if b["status"] == "draft"]),
            "finalized_bhts": len([b for b in enriched_bhts if b["status"] == "finalized"]),
            "approved_bhts": len([b for b in enriched_bhts if b["status"] == "approved"]),
            "rejected_bhts": len([b for b in enriched_bhts if b["status"] == "rejected"])
        }
    }


@router.post("/consultants/patients/{patient_id}/review")
def review_patient_for_discharge(
    patient_id: str,
    review: PatientReviewAction,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """
    Approve or reject a patient's discharge based on summary review.
    
    Actions:
    - "approve": Approve summary, mark patient ready for discharge
    - "reject": Reject summary, send back to doctor for revision
    
    This updates the patient summary status and can optionally update BHT statuses.
    """
    consultant_id = current_user["user_id"]
    
    if review.action not in ["approve", "reject"]:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Action must be 'approve' or 'reject'"
        )
    
    if review.action == "reject" and not review.rejection_reason:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Rejection reason is required when rejecting"
        )
    
    # Verify patient exists and is in consultant's ward
    patient_resp = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
    if not patient_resp.data:
        raise fastapi.HTTPException(status_code=404, detail="Patient not found")
    
    patient = patient_resp.data[0]
    
    # Check ward ownership
    ward_resp = supabase.table("wards").select("*").eq("ward_id", patient["ward_id"]).execute()
    if not ward_resp.data or ward_resp.data[0]["consultant_id"] != consultant_id:
        raise fastapi.HTTPException(
            status_code=403,
            detail="You do not manage this patient's ward"
        )
    
    # Get summary
    summary_resp = supabase.table("llm_reports").select("*").eq("patient_id", patient_id).execute()
    if not summary_resp.data:
        raise fastapi.HTTPException(
            status_code=404,
            detail="No summary found for this patient"
        )
    
    summary = summary_resp.data[0]
    
    if summary["status"] != "submitted":
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Cannot review summary with status '{summary['status']}'. Only 'submitted' summaries can be reviewed."
        )
    
    now = datetime.utcnow().isoformat()
    
    if review.action == "approve":
        # Approve the summary
        supabase.table("llm_reports").update({
            "status": "approved",
            "updated_at": now
        }).eq("report_id", summary["report_id"]).execute()
        
        # Optionally approve all finalized BHTs
        bhts_resp = supabase.table("bht_records").select("*").eq("patient_id", patient_id).eq("status", "finalized").execute()
        approved_bhts_count = 0
        
        for bht in bhts_resp.data:
            supabase.table("bht_records").update({
                "status": "approved",
                "approved_by_consultant_id": consultant_id,
                "updated_at": now
            }).eq("bht_id", bht["bht_id"]).execute()
            approved_bhts_count += 1
        
        return {
            "success": True,
            "action": "approved",
            "patient_id": patient_id,
            "patient_name": patient["name"],
            "summary_status": "approved",
            "approved_bhts": approved_bhts_count,
            "approved_by": consultant_id,
            "approved_at": now,
            "notes": review.notes,
            "message": "Patient approved for discharge"
        }
    
    else:  # reject
        # Reject the summary - send back to doctor
        supabase.table("llm_reports").update({
            "status": "rejected",
            "updated_at": now
        }).eq("report_id", summary["report_id"]).execute()
        
        # Mark BHTs as rejected
        bhts_resp = supabase.table("bht_records").select("*").eq("patient_id", patient_id).eq("status", "finalized").execute()
        rejected_bhts_count = 0
        
        for bht in bhts_resp.data:
            supabase.table("bht_records").update({
                "status": "rejected",
                "rejected_by_consultant_id": consultant_id,
                "rejection_reason": review.rejection_reason,
                "rejected_date": now,
                "updated_at": now
            }).eq("bht_id", bht["bht_id"]).execute()
            rejected_bhts_count += 1
        
        return {
            "success": True,
            "action": "rejected",
            "patient_id": patient_id,
            "patient_name": patient["name"],
            "summary_status": "rejected",
            "rejected_bhts": rejected_bhts_count,
            "rejected_by": consultant_id,
            "rejected_at": now,
            "rejection_reason": review.rejection_reason,
            "notes": review.notes,
            "message": "Patient summary rejected. Doctor can revise and resubmit."
        }
