"""
HYBRID OCR PIPELINE ORCHESTRATOR

Coordinates the two-stage hybrid pipeline:
- Stage 1: Gemini OCR extraction (ocr_extractor module)
- Stage 2: Gemini semantic structuring (text_structurer module)

Also provides legacy Gemini-vision-only fallback and patient summarization.
"""

from typing import Optional, Dict, List
import io
import os
import json

import dotenv

dotenv.load_dotenv()

# Import modules
from utils.ocr_extractor import extract_raw_text_with_gemini_ocr
from utils.text_structurer import (
    BHTExtractedData,
    structure_raw_ocr_text_with_gemini,
    extract_image_with_gemini_vision,
    get_bht_semantic_correction_prompt_template,
    get_bht_extraction_output_schema,
)

# Gemini imports
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None



def get_bht_extraction_spec():
    """Return canonical prompt template and output schema for cross-model evaluation."""
    return {
        "task": "bht_ocr_semantic_structuring",
        "prompt_template": get_bht_semantic_correction_prompt_template(),
        "output_schema": get_bht_extraction_output_schema(),
        "notes": [
            "Use the same prompt_template and output_schema for all models.",
            "Replace {{RAW_OCR_TEXT}} with OCR text from your chosen OCR stage.",
            "Require model output as strict JSON only.",
        ],
    }



def extract_text_with_hybrid_pipeline(file) -> BHTExtractedData:
    """
    ═══════════════════════════════════════════════════════════════════
    HYBRID OCR PIPELINE: Gemini OCR + Gemini Semantic Structuring
    ═══════════════════════════════════════════════════════════════════
    
    Complete two-stage hybrid pipeline for BHT medical record extraction:
    
    **Stage 1 (OCR Extraction)**:
    - Input: BHT image (handwritten medical record)
    - Method: Gemini Vision OCR text extraction
    - Output: Raw noisy text with potential transcription errors
    
    **Stage 2 (Semantic Post-Correction)**:
    - Input: Raw OCR text from Stage 1
    - Method: Gemini 2.5 Flash with medical domain knowledge
    - Output: Corrected, structured, and validated medical data
    
        **Fallback Strategy**:
        - If Gemini OCR fails or produces poor results (<10 chars), automatically
            falls back to Gemini's native vision understanding for direct
            image-to-structured-data extraction
    
    This hybrid approach combines:
    - Gemini OCR text extraction
    - Gemini's semantic understanding and medical knowledge
    - Gemini's vision understanding as a robust fallback
    
    Args:
        file: UploadFile object containing the BHT image
        
    Returns:
        BHTExtractedData: Validated structured medical record with confidence score
    """
    print("\n" + "="*70)
    print("HYBRID PIPELINE: Gemini OCR + Gemini Semantic Structuring")
    print("="*70)
    
    ocr_failed = False
    raw_ocr_text = None
    
    try:
        # ═══════════════════════════════════════════════════════════════
        # STAGE 1: OCR EXTRACTION
        # ═══════════════════════════════════════════════════════════════
        print("\n[STAGE 1] Extracting raw text with Gemini OCR...")
        try:
            raw_ocr_text = extract_raw_text_with_gemini_ocr(file)
            
            # Check if OCR output is too short or empty
            if not raw_ocr_text or len(raw_ocr_text.strip()) < 10:
                print(f"[WARNING] OCR output too short ({len(raw_ocr_text.strip()) if raw_ocr_text else 0} chars).")
                print("Falling back to Gemini vision...")
                ocr_failed = True
        except Exception as ocr_error:
            print(f"[WARNING] Gemini OCR failed: {ocr_error}")
            print("Falling back to Gemini vision...")
            ocr_failed = True
        
        # ═══════════════════════════════════════════════════════════════
        # FALLBACK: Direct Gemini Vision
        # ═══════════════════════════════════════════════════════════════
        if ocr_failed:
            print("\n[FALLBACK] Using Gemini vision for direct extraction...")
            if hasattr(file.file, 'seek'):
                file.file.seek(0)
            structured_data = extract_image_with_gemini_vision(file)
            
            print("\n" + "="*70)
            print("FALLBACK COMPLETE (Gemini Vision Only)")
            print("="*70)
            print(f"Fields Extracted: {sum(1 for k, v in structured_data.model_dump().items() if v is not None)}")
            print(f"Confidence: {structured_data.confidence_score}")
            print("="*70 + "\n")
            
            return structured_data
        
        # ═══════════════════════════════════════════════════════════════
        # STAGE 2: SEMANTIC POST-CORRECTION
        # ═══════════════════════════════════════════════════════════════
        print("\n[STAGE 2] Structuring with Gemini semantic correction...")
        structured_data = structure_raw_ocr_text_with_gemini(raw_ocr_text)
        
        print("\n" + "="*70)
        print("HYBRID PIPELINE COMPLETE")
        print("="*70)
        print(f"Raw OCR Length: {len(raw_ocr_text)} chars")
        print(f"Fields Extracted: {sum(1 for k, v in structured_data.model_dump().items() if v is not None)}")
        print(f"Confidence: {structured_data.confidence_score}")
        print("="*70 + "\n")
        
        return structured_data
        
    except Exception as e:
        print(f"\n[ERROR] Hybrid pipeline failed: {e}")
        
        # Last resort: Try Gemini vision if we haven't already
        if not ocr_failed:
            try:
                print("\n[LAST RESORT] Attempting Gemini vision...")
                if hasattr(file.file, 'seek'):
                    file.file.seek(0)
                return extract_image_with_gemini_vision(file)
            except Exception as fallback_error:
                print(f"[ERROR] Fallback also failed: {fallback_error}")
        raise e


def extract_text_with_gemini(file) -> BHTExtractedData:
    """LEGACY: Direct Gemini vision-based extraction.
    
    This is kept for backward compatibility but the hybrid pipeline
    (extract_text_with_hybrid_pipeline) is recommended for better accuracy.
    
    Args:
        file: UploadFile object containing the BHT image
        
    Returns:
        BHTExtractedData: Extracted and structured medical record data
    """
    return extract_image_with_gemini_vision(file)


def _strip_recommendations_section(summary_text: str) -> str:
    """Remove a trailing recommendations section from generated summaries.

    The model may still include recommendations even when instructed not to.
    This keeps the report focused on summary-only content.
    """
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
    """Generate a comprehensive patient summary using all BHT records with Gemini.
    
    Args:
        patient: Patient dictionary with demographic information
        bht_records: List of BHT record dictionaries
    
    Returns:
        A comprehensive markdown-formatted patient summary
    """
    try:
        if genai is None:
            raise RuntimeError("google.genai is not installed. Please install it with: pip install google-genai")
        
        # Prepare patient context
        patient_info = f"""
Patient Information:
- Name: {patient.get('name', 'N/A')}
- Patient ID: {patient.get('patient_id', 'N/A')}
- Date of Birth: {patient.get('dob', 'N/A')}
- Gender: {patient.get('gender', 'N/A')}
- Ward ID: {patient.get('ward_id', 'N/A')}
- Admission Date: {patient.get('admission_date', 'N/A')}
"""
        
        # Prepare BHT records summary
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
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
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
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        return _strip_recommendations_section(response.text)
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        raise e
