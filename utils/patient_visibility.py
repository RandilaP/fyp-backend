from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from util.supabse import supabase


def get_latest_bht_status_map(patient_ids: Iterable[str]) -> Dict[str, Optional[str]]:
    patient_id_list = [patient_id for patient_id in patient_ids if patient_id]
    if not patient_id_list:
        return {}

    response = (
        supabase.table("bht_records")
        .select("patient_id, status, upload_date")
        .in_("patient_id", patient_id_list)
        .order("upload_date", desc=True)
        .execute()
    )

    latest_status_by_patient: Dict[str, Optional[str]] = {}
    for record in response.data:
        patient_id = record.get("patient_id")
        if patient_id and patient_id not in latest_status_by_patient:
            latest_status_by_patient[patient_id] = record.get("status")

    return latest_status_by_patient


def filter_active_patients(patients: List[dict]) -> List[dict]:
    latest_status_by_patient = get_latest_bht_status_map(
        patient.get("patient_id") for patient in patients
    )

    active_patients: List[dict] = []
    for patient in patients:
        latest_status = latest_status_by_patient.get(patient.get("patient_id"))
        if patient.get("discharge_date"):
            continue
        if latest_status == "approved":
            continue
        active_patients.append(patient)

    return active_patients