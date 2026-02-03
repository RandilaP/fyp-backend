import fastapi
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from util.supabse import supabase
from api.auth import get_current_user


router = fastapi.APIRouter()


class PerformanceMetrics(BaseModel):
    """System performance analytics for technical evaluation (FR6)."""
    total_records_processed: int
    finalized_records: int
    rejected_records: int
    draft_records: int
    
    # Processing Latency Metrics
    average_processing_latency_hours: Optional[float]
    median_processing_latency_hours: Optional[float]
    min_processing_latency_hours: Optional[float]
    max_processing_latency_hours: Optional[float]
    
    # OCR Quality Metrics (Objective R07)
    average_word_error_rate: Optional[float]
    average_ner_f1_score: Optional[float]
    
    # Additional Performance Indicators
    throughput_records_per_day: Optional[float]
    success_rate_percentage: Optional[float]
    
    # Time range for the analysis
    analysis_period_start: Optional[str]
    analysis_period_end: Optional[str]
    
    # Detailed breakdown
    processing_latency_distribution: Optional[dict]
    status_breakdown: Optional[dict]


class RecordPerformanceDetail(BaseModel):
    """Individual record performance detail."""
    bht_id: str
    patient_id: str
    upload_date: str
    finalized_date: Optional[str]
    processing_latency_hours: Optional[float]
    wer: Optional[float]
    ner_f1_score: Optional[float]
    status: str


def calculate_processing_latency(upload_date: str, finalized_date: Optional[str]) -> Optional[float]:
    """
    Calculate processing latency in hours between upload and finalization.
    
    Args:
        upload_date: ISO format datetime of record upload
        finalized_date: ISO format datetime of finalization
        
    Returns:
        Processing latency in hours, or None if not finalized
    """
    if not finalized_date:
        return None
    
    try:
        upload_dt = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
        finalized_dt = datetime.fromisoformat(finalized_date.replace('Z', '+00:00'))
        
        latency_seconds = (finalized_dt - upload_dt).total_seconds()
        latency_hours = latency_seconds / 3600
        
        return round(latency_hours, 2)
    except Exception as e:
        print(f"Error calculating latency: {e}")
        return None


@router.get("/analytics/performance", response_model=PerformanceMetrics)
def get_performance_analytics(
    start_date: Optional[str] = fastapi.Query(None, description="Start date for analysis (ISO format)"),
    end_date: Optional[str] = fastapi.Query(None, description="End date for analysis (ISO format)"),
    current_user: dict = fastapi.Depends(get_current_user)
):
    """
    Get system performance analytics for technical evaluation (FR6 - Objective R07).
    
    This endpoint analyzes the hybrid OCR-NLP pipeline performance by aggregating:
    - Processing Latency: Time between upload_date and finalized_date
    - Word Error Rate (WER): Average OCR accuracy metric
    - F1-Score for NER: Named Entity Recognition performance
    
    Returns JSON summary suitable for the 'Results' chapter of technical reports.
    
    Args:
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        current_user: Authenticated user
        
    Returns:
        Comprehensive performance metrics including latency, WER, and NER F1-scores
    """
    # Build query
    query = supabase.table("bht_records").select("*")
    
    # Apply date filters if provided
    if start_date:
        query = query.gte("upload_date", start_date)
    if end_date:
        query = query.lte("upload_date", end_date)
    
    # Fetch all records
    resp = query.execute()
    records = resp.data
    
    if not records:
        return PerformanceMetrics(
            total_records_processed=0,
            finalized_records=0,
            rejected_records=0,
            draft_records=0,
            average_processing_latency_hours=None,
            median_processing_latency_hours=None,
            min_processing_latency_hours=None,
            max_processing_latency_hours=None,
            average_word_error_rate=None,
            average_ner_f1_score=None,
            throughput_records_per_day=None,
            success_rate_percentage=None,
            analysis_period_start=start_date,
            analysis_period_end=end_date,
            processing_latency_distribution=None,
            status_breakdown=None
        )
    
    # Calculate metrics
    total_records = len(records)
    finalized_records = [r for r in records if r["status"] == "finalized"]
    rejected_records = [r for r in records if r["status"] == "rejected"]
    draft_records = [r for r in records if r["status"] == "draft"]
    
    # Processing Latency Calculation
    latencies = []
    for record in finalized_records:
        latency = calculate_processing_latency(
            record.get("upload_date"), 
            record.get("finalized_date")
        )
        if latency is not None:
            latencies.append(latency)
    
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None
    median_latency = None
    min_latency = None
    max_latency = None
    
    if latencies:
        sorted_latencies = sorted(latencies)
        median_latency = round(sorted_latencies[len(sorted_latencies) // 2], 2)
        min_latency = round(min(latencies), 2)
        max_latency = round(max(latencies), 2)
    
    # OCR Quality Metrics (WER and NER F1-Score)
    wer_values = [r.get("wer") for r in records if r.get("wer") is not None]
    ner_f1_values = [r.get("ner_f1_score") for r in records if r.get("ner_f1_score") is not None]
    
    avg_wer = round(sum(wer_values) / len(wer_values), 4) if wer_values else None
    avg_ner_f1 = round(sum(ner_f1_values) / len(ner_f1_values), 4) if ner_f1_values else None
    
    # Throughput calculation (records per day)
    throughput = None
    if records and len(records) > 1:
        try:
            earliest = min(datetime.fromisoformat(r["upload_date"].replace('Z', '+00:00')) for r in records)
            latest = max(datetime.fromisoformat(r["upload_date"].replace('Z', '+00:00')) for r in records)
            days = (latest - earliest).total_seconds() / 86400
            if days > 0:
                throughput = round(total_records / days, 2)
        except Exception as e:
            print(f"Error calculating throughput: {e}")
    
    # Success rate (finalized / total)
    success_rate = round((len(finalized_records) / total_records) * 100, 2) if total_records > 0 else 0
    
    # Latency distribution
    latency_distribution = None
    if latencies:
        latency_distribution = {
            "0-1_hours": len([l for l in latencies if l <= 1]),
            "1-6_hours": len([l for l in latencies if 1 < l <= 6]),
            "6-24_hours": len([l for l in latencies if 6 < l <= 24]),
            "24-72_hours": len([l for l in latencies if 24 < l <= 72]),
            "over_72_hours": len([l for l in latencies if l > 72])
        }
    
    # Status breakdown
    status_breakdown = {
        "finalized": len(finalized_records),
        "rejected": len(rejected_records),
        "draft": len(draft_records)
    }
    
    return PerformanceMetrics(
        total_records_processed=total_records,
        finalized_records=len(finalized_records),
        rejected_records=len(rejected_records),
        draft_records=len(draft_records),
        average_processing_latency_hours=avg_latency,
        median_processing_latency_hours=median_latency,
        min_processing_latency_hours=min_latency,
        max_processing_latency_hours=max_latency,
        average_word_error_rate=avg_wer,
        average_ner_f1_score=avg_ner_f1,
        throughput_records_per_day=throughput,
        success_rate_percentage=success_rate,
        analysis_period_start=start_date,
        analysis_period_end=end_date,
        processing_latency_distribution=latency_distribution,
        status_breakdown=status_breakdown
    )


@router.get("/analytics/records", response_model=List[RecordPerformanceDetail])
def get_record_performance_details(
    status: Optional[str] = fastapi.Query(None, description="Filter by status: finalized, rejected, draft"),
    min_latency_hours: Optional[float] = fastapi.Query(None, description="Minimum processing latency in hours"),
    max_latency_hours: Optional[float] = fastapi.Query(None, description="Maximum processing latency in hours"),
    current_user: dict = fastapi.Depends(get_current_user)
):
    """
    Get detailed performance metrics for individual BHT records.
    
    Useful for identifying outliers and understanding performance distribution.
    
    Args:
        status: Optional filter by record status
        min_latency_hours: Optional minimum latency filter
        max_latency_hours: Optional maximum latency filter
        current_user: Authenticated user
        
    Returns:
        List of records with individual performance metrics
    """
    # Build query
    query = supabase.table("bht_records").select("*")
    
    if status:
        query = query.eq("status", status)
    
    resp = query.execute()
    records = resp.data
    
    # Process records and calculate individual metrics
    details = []
    for record in records:
        latency = calculate_processing_latency(
            record.get("upload_date"),
            record.get("finalized_date")
        )
        
        # Apply latency filters
        if min_latency_hours is not None and (latency is None or latency < min_latency_hours):
            continue
        if max_latency_hours is not None and (latency is None or latency > max_latency_hours):
            continue
        
        details.append(RecordPerformanceDetail(
            bht_id=record["bht_id"],
            patient_id=record["patient_id"],
            upload_date=record["upload_date"],
            finalized_date=record.get("finalized_date"),
            processing_latency_hours=latency,
            wer=record.get("wer"),
            ner_f1_score=record.get("ner_f1_score"),
            status=record["status"]
        ))
    
    # Sort by latency (descending) if latency data exists
    details.sort(
        key=lambda x: x.processing_latency_hours if x.processing_latency_hours is not None else -1,
        reverse=True
    )
    
    return details
