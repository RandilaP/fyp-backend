import fastapi
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from api.auth import get_current_user, require_role
from util.supabse import supabase
from models.bht_record import BHTRecordResponse
import json


router = fastapi.APIRouter()


class ApprovalRequest(BaseModel):
    """Request model for approving a BHT record."""
    notes: Optional[str] = None


class RejectionRequest(BaseModel):
    """Request model for rejecting a BHT record."""
    rejection_reason: str


class EIMMRExport(BaseModel):
    """e-IMMR (Electronic Integrated Medical Record) export format."""
    record_id: str
    patient_id: str
    admission_date: Optional[str]
    discharge_date: Optional[str]
    diagnosis: Optional[str]
    symptoms: Optional[str]
    treatment_plan: Optional[str]
    medications: Optional[str]
    vitals: Optional[dict]
    procedures: Optional[str]
    lab_results: Optional[dict]
    notes: Optional[str]
    approved_by: str
    approval_timestamp: str
    bed_occupancy_data: Optional[dict]


def calculate_bed_occupancy_metrics(admission_date: Optional[str], discharge_timestamp: str) -> dict:
    """
    Calculate bed occupancy metrics for hospital KPIs.
    
    Args:
        admission_date: ISO format datetime of patient admission
        discharge_timestamp: ISO format datetime of discharge
        
    Returns:
        Dictionary containing BOR metrics
    """
    if not admission_date:
        return {
            "length_of_stay_hours": None,
            "length_of_stay_days": None
        }
    
    try:
        admission_dt = datetime.fromisoformat(admission_date.replace('Z', '+00:00'))
        discharge_dt = datetime.fromisoformat(discharge_timestamp.replace('Z', '+00:00'))
        
        los_hours = (discharge_dt - admission_dt).total_seconds() / 3600
        los_days = los_hours / 24
        
        return {
            "length_of_stay_hours": round(los_hours, 2),
            "length_of_stay_days": round(los_days, 2),
            "admission_timestamp": admission_date,
            "discharge_timestamp": discharge_timestamp
        }
    except Exception as e:
        print(f"Error calculating bed occupancy: {e}")
        return {
            "length_of_stay_hours": None,
            "length_of_stay_days": None,
            "error": str(e)
        }


def generate_eimmr_export(record: dict, consultant_id: str) -> EIMMRExport:
    """
    Generate e-IMMR format export for approved BHT record.
    
    Args:
        record: BHT record dictionary from database
        consultant_id: ID of the approving consultant
        
    Returns:
        EIMMRExport object with standardized medical record format
    """
    # Fetch patient data for admission date
    patient_resp = supabase.table("patients").select("admission_date").eq("patient_id", record["patient_id"]).execute()
    admission_date = patient_resp.data[0]["admission_date"] if patient_resp.data else None
    
    discharge_timestamp = record.get("discharge_timestamp") or datetime.utcnow().isoformat()
    
    bed_occupancy_data = calculate_bed_occupancy_metrics(admission_date, discharge_timestamp)
    
    return EIMMRExport(
        record_id=record["bht_id"],
        patient_id=record["patient_id"],
        admission_date=admission_date,
        discharge_date=discharge_timestamp,
        diagnosis=record.get("diagnosis"),
        symptoms=record.get("symptoms"),
        treatment_plan=record.get("treatment_plan"),
        medications=record.get("medications"),
        vitals=record.get("vitals"),
        procedures=record.get("procedures"),
        lab_results=record.get("lab_results"),
        notes=record.get("notes"),
        approved_by=consultant_id,
        approval_timestamp=datetime.utcnow().isoformat(),
        bed_occupancy_data=bed_occupancy_data
    )


@router.post("/bht_records/{record_id}/approve", response_model=dict)
def approve_bht_record(
    record_id: str,
    approval_request: ApprovalRequest,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """
    Approve a BHT record and finalize it (FR3 - Digital Approval & Sign-Off Workflow).
    
    This endpoint:
    1. Verifies the consultant's role from JWT
    2. Updates status to 'finalized'
    3. Records discharge_timestamp for BOR calculation
    4. Triggers automatic e-IMMR export
    
    Args:
        record_id: UUID of the BHT record to approve
        approval_request: Optional approval notes
        current_user: Authenticated user with Consultant or Admin role
        
    Returns:
        Approval confirmation with e-IMMR export data
        
    Raises:
        404: Record not found
        400: Record already finalized or rejected
    """
    # Fetch the BHT record
    resp = supabase.table("bht_records").select("*").eq("bht_id", record_id).execute()
    
    if not resp.data:
        raise fastapi.HTTPException(status_code=404, detail="BHT record not found")
    
    record = resp.data[0]
    
    # Check if already finalized or rejected
    if record["status"] in ["finalized", "rejected"]:
        raise fastapi.HTTPException(
            status_code=400, 
            detail=f"Record already {record['status']}. Cannot approve."
        )
    
    # Prepare update data
    now = datetime.utcnow().isoformat()
    update_data = {
        "status": "finalized",
        "approved_by_consultant_id": current_user["user_id"],
        "finalized_date": now,
        "discharge_timestamp": now,
        "updated_at": now
    }
    
    if approval_request.notes:
        current_notes = record.get("notes", "")
        update_data["notes"] = f"{current_notes}\n\n[APPROVAL NOTE] {approval_request.notes}".strip()
    
    # Update the record
    update_resp = supabase.table("bht_records").update(update_data).eq("bht_id", record_id).execute()
    
    if not update_resp.data:
        raise fastapi.HTTPException(status_code=500, detail="Failed to approve record")
    
    updated_record = update_resp.data[0]
    
    # Generate e-IMMR export
    eimmr_export = generate_eimmr_export(updated_record, current_user["user_id"])
    
    # Store e-IMMR export in a separate table (optional - for audit trail)
    try:
        supabase.table("eimmr_exports").insert({
            "bht_id": record_id,
            "export_data": eimmr_export.dict(),
            "exported_by": current_user["user_id"],
            "exported_at": now
        }).execute()
    except Exception as e:
        # Log but don't fail if export table doesn't exist
        print(f"Warning: Could not store e-IMMR export: {e}")
    
    return {
        "success": True,
        "message": "BHT record approved and finalized successfully",
        "record_id": record_id,
        "status": "finalized",
        "approved_by": current_user["name"],
        "finalized_date": now,
        "eimmr_export": eimmr_export.dict(),
        "bed_occupancy_metrics": eimmr_export.bed_occupancy_data
    }


@router.post("/bht_records/{record_id}/reject", response_model=dict)
def reject_bht_record(
    record_id: str,
    rejection_request: RejectionRequest,
    current_user: dict = fastapi.Depends(require_role("Consultant", "Admin"))
):
    """
    Reject a BHT record with mandatory reason (FR3 - Digital Approval & Sign-Off Workflow).
    
    This endpoint:
    1. Verifies the consultant's role from JWT
    2. Updates status to 'rejected'
    3. Records rejection reason
    4. Notifies the House Officer (logged for future implementation)
    
    Args:
        record_id: UUID of the BHT record to reject
        rejection_request: Contains mandatory rejection_reason
        current_user: Authenticated user with Consultant or Admin role
        
    Returns:
        Rejection confirmation with reason
        
    Raises:
        404: Record not found
        400: Record already finalized or rejected
    """
    # Fetch the BHT record
    resp = supabase.table("bht_records").select("*").eq("bht_id", record_id).execute()
    
    if not resp.data:
        raise fastapi.HTTPException(status_code=404, detail="BHT record not found")
    
    record = resp.data[0]
    
    # Check if already finalized or rejected
    if record["status"] in ["finalized", "rejected"]:
        raise fastapi.HTTPException(
            status_code=400, 
            detail=f"Record already {record['status']}. Cannot reject."
        )
    
    # Prepare update data
    now = datetime.utcnow().isoformat()
    update_data = {
        "status": "rejected",
        "rejected_by_consultant_id": current_user["user_id"],
        "rejection_reason": rejection_request.rejection_reason,
        "rejected_date": now,
        "updated_at": now
    }
    
    # Update the record
    update_resp = supabase.table("bht_records").update(update_data).eq("bht_id", record_id).execute()
    
    if not update_resp.data:
        raise fastapi.HTTPException(status_code=500, detail="Failed to reject record")
    
    updated_record = update_resp.data[0]
    
    house_officer_id = updated_record.get("doctor_id")
    notification_logged = False
    
    try:
        # Log notification in audit_log table (if exists)
        supabase.table("audit_log").insert({
            "action": "bht_rejected",
            "entity_type": "bht_record",
            "entity_id": record_id,
            "performed_by": current_user["user_id"],
            "target_user": house_officer_id,
            "details": {
                "rejection_reason": rejection_request.rejection_reason,
                "rejected_by": current_user["name"]
            },
            "timestamp": now
        }).execute()
        notification_logged = True
    except Exception as e:
        print(f"Warning: Could not log notification: {e}")
    
    return {
        "success": True,
        "message": "BHT record rejected successfully",
        "record_id": record_id,
        "status": "rejected",
        "rejected_by": current_user["name"],
        "rejection_reason": rejection_request.rejection_reason,
        "rejected_date": now,
        "house_officer_notified": notification_logged,
        "house_officer_id": house_officer_id
    }
