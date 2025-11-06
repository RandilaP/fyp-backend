import fastapi
from models.llm_report import LLMReportCreate, LLMReportResponse
from util.supabse import supabase

router = fastapi.APIRouter()

@router.post("/llm_reports/", response_model=LLMReportResponse)
def create_llm_report(report: LLMReportCreate):
    data = report.dict()
    response = supabase.table("llm_reports").insert(data).execute()
    return LLMReportResponse(**response.data[0])

@router.get("/llm_reports/{report_id}", response_model=LLMReportResponse)
def get_llm_report(report_id: str):
    response = supabase.table("llm_reports").select("*").eq("report_id", report_id).execute()
    return LLMReportResponse(**response.data[0])

@router.get("/llm_reports/", response_model=list[LLMReportResponse])
def list_llm_reports():
    response = supabase.table("llm_reports").select("*").execute()
    return [LLMReportResponse(**report) for report in response.data]

