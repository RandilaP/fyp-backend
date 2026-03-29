"""LLM report generation service (Gemini-first)."""

import os

import dotenv

dotenv.load_dotenv()

try:
    from google import genai
except ImportError:
    genai = None


GEMINI_SUMMARY_MODEL = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-2.5-flash")


def _strip_recommendations_section(summary_text: str) -> str:
    """Remove recommendations section if model includes it."""
    if not summary_text:
        return summary_text

    lines = summary_text.splitlines()
    cleaned_lines = []
    stop_at_recommendations = False

    for line in lines:
        normalized = line.strip().lower()
        is_recommendations_heading = (
            normalized.startswith("9.") and "recommendation" in normalized
        ) or (
            normalized.startswith("##") and "recommendation" in normalized
        ) or (
            normalized.startswith("**recommendation")
        ) or (
            normalized == "recommendations"
        )

        if is_recommendations_heading:
            stop_at_recommendations = True
            continue

        if stop_at_recommendations:
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def generate_patient_summary_with_gemini(patient: dict, bht_records: list) -> str:
    """Generate a comprehensive patient summary from chronological BHT records."""
    if genai is None:
        raise RuntimeError("google.genai is not installed. Please install it with: pip install google-genai")

    patient_info = f"""
Patient Information:
- Name: {patient.get('name', 'N/A')}
- Patient ID: {patient.get('patient_id', 'N/A')}
- Date of Birth: {patient.get('dob', 'N/A')}
- Gender: {patient.get('gender', 'N/A')}
- Ward ID: {patient.get('ward_id', 'N/A')}
- Admission Date: {patient.get('admission_date', 'N/A')}
"""

    bht_summary = "\n\nBHT Records (chronological order):\n\n"
    for idx, bht in enumerate(bht_records, 1):
        bht_summary += f"""Record #{idx} (Uploaded: {bht.get('upload_date', 'N/A')}):
- Diagnosis: {bht.get('diagnosis', 'N/A')}
- Symptoms: {bht.get('symptoms', 'N/A')}
- Treatment Plan: {bht.get('treatment_plan', 'N/A')}
- Medications: {bht.get('medications', 'N/A')}
- Vitals: {bht.get('vitals', 'N/A')}
- Procedures: {bht.get('procedures', 'N/A')}
- Lab Results: {bht.get('lab_results', 'N/A')}
- Notes: {bht.get('notes', 'N/A')}

"""

    prompt = f"""{patient_info}{bht_summary}

Based on the above patient information and BHT records, generate a comprehensive medical summary that includes:

1. **Patient Overview**: Brief demographic summary and admission details
2. **Medical History**: Chronological progression of the patient's condition based on BHT records
3. **Current Diagnosis**: Primary diagnoses and any comorbidities identified
4. **Treatment Course**: Summary of treatments administered, including medications and procedures
5. **Clinical Progress**: How the patient's condition has evolved over time
6. **Vital Signs Trends**: Any notable patterns or changes in vital signs
7. **Laboratory Findings**: Summary of significant lab results and their implications
8. **Current Status**: The patient's current condition based on the most recent BHT

Do not include a recommendations section.
Format the summary in clear, professional medical language suitable for consultant review. Use markdown formatting for better readability.
"""

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=GEMINI_SUMMARY_MODEL,
        contents=prompt,
    )

    return _strip_recommendations_section(response.text)
