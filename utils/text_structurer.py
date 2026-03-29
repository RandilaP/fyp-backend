"""
TEXT STRUCTURER MODULE - Stage 2 of the Hybrid Pipeline

Semantic correction and structuring using Gemini's RAG capabilities.
Takes raw OCR text (or image for fallback) and returns structured medical data.
"""

import os
import io
import json
from typing import Optional, Dict
from pydantic import BaseModel, Field

import dotenv

dotenv.load_dotenv()

# Gemini imports
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class BHTExtractedData(BaseModel):
    """Structured data extracted from a BHT (Bed Head Ticket) medical record image."""
    
    diagnosis: Optional[str] = Field(
        default=None,
        description="The primary diagnosis or medical condition identified in the BHT. Include ICD codes if visible."
    )
    symptoms: Optional[str] = Field(
        default=None,
        description="List of symptoms or complaints documented in the BHT. Include onset, duration, and severity if mentioned."
    )
    treatment_plan: Optional[str] = Field(
        default=None,
        description="The treatment plan or care instructions documented in the BHT. Include dosages, frequencies, and durations."
    )
    medications: Optional[str] = Field(
        default=None,
        description="List of medications prescribed or administered. Include drug names, dosages, routes, and frequencies."
    )
    vitals: Optional[Dict] = Field(
        default=None,
        description="Vital signs recorded in the BHT. Should include values like temperature, blood pressure, heart rate, respiratory rate, oxygen saturation, etc."
    )
    procedures: Optional[str] = Field(
        default=None,
        description="Medical procedures performed or planned. Include procedure names, dates, and any relevant details."
    )
    lab_results: Optional[Dict] = Field(
        default=None,
        description="Laboratory test results documented in the BHT. Include test names and their values with units."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional clinical notes, observations, or remarks from healthcare providers."
    )
    raw_ocr_text: Optional[str] = Field(
        default=None,
        description="Raw OCR output before semantic post-correction (populated in hybrid mode)."
    )
    ocr_engine: Optional[str] = Field(
        default=None,
        description="OCR engine used for raw text extraction (e.g., gemini, trocr)."
    )
    confidence_score: Optional[float] = Field(
        default=None,
        description="Confidence score of the extraction process (0.0 to 1.0)."
    )
    
    class Config:
        # Allow population by field name
        populate_by_name = True


def get_bht_extraction_output_schema() -> dict:
    """Return the canonical JSON schema for structured BHT extraction output."""
    return clean_schema_for_gemini(BHTExtractedData.model_json_schema())


def clean_schema_for_gemini(schema: dict) -> dict:
    """
    Clean JSON schema for Gemini API compatibility.
    Removes 'additionalProperties' and 'default'/'default_factory' which are not supported.
    
    Args:
        schema: JSON schema dictionary generated from Pydantic model
        
    Returns:
        Cleaned schema dictionary compatible with Gemini
    """
    if isinstance(schema, dict):
        # Remove unsupported fields
        schema = {k: v for k, v in schema.items() if k not in ('additionalProperties', 'default', 'default_factory')}
        
        # Recursively clean nested in each field
        if 'properties' in schema and isinstance(schema['properties'], dict):
            for field_name, field_schema in schema['properties'].items():
                if isinstance(field_schema, dict):
                    # Remove defaults from each field definition
                    schema['properties'][field_name] = {k: v for k, v in field_schema.items() if k not in ('default', 'default_factory')}
                    # Recursively clean nested structures
                    schema['properties'][field_name] = clean_schema_for_gemini(schema['properties'][field_name])
        
        # Recursively clean other dict values
        for key, value in list(schema.items()):
            if isinstance(value, dict) and key not in ('properties',):  # Already handled properties
                schema[key] = clean_schema_for_gemini(value)
            elif isinstance(value, list):
                schema[key] = [clean_schema_for_gemini(item) if isinstance(item, dict) else item for item in value]
    
    return schema


def get_bht_semantic_correction_prompt(raw_text: str) -> str:
    """Build the canonical prompt used for OCR-text to structured JSON conversion."""
    return f"""
You are a medical AI assistant for a Sri Lankan hospital's BHT (Bed Head Ticket) digitization system.

TASK: Semantic Post-Correction and Structuring

You have received NOISY OCR OUTPUT from a handwritten medical record. Your job is to:

1. Fix transcription errors in medical terms, drug names, and clinical abbreviations.
2. Expand Sri Lankan medical abbreviations:
   - BD/BID -> twice daily
   - TDS/TID -> three times daily
   - QDS/QID -> four times daily
   - PRN -> as needed
   - PO -> oral route
   - IV -> intravenous
   - IM -> intramuscular
   - SC -> subcutaneous
   - STAT -> immediately
   - OD -> once daily
   - HS -> at bedtime
3. Structure the corrected text into the specified JSON fields
4. Set confidence_score between 0.0 (low confidence) and 1.0 (high confidence) based on clarity and completeness

NOISY OCR INPUT:
{raw_text}

IMPORTANT:
- Return ONLY valid JSON. No markdown, no explanations.
- Only correct obvious OCR mistakes. Do not hallucinate data.
- If a field cannot be determined, set it to null.
- Preserve units for all numeric measurements.
- Keep medical meaning and chronology intact.
- Set confidence_score based on how clear and complete the extracted data is (0.0-1.0).
""".strip()


def get_bht_semantic_correction_prompt_template() -> str:
    """Return prompt template for external model testing with placeholder input."""
    return get_bht_semantic_correction_prompt("{{RAW_OCR_TEXT}}")


def structure_raw_ocr_text_with_gemini(raw_text: str) -> BHTExtractedData:
    """
    ═══════════════════════════════════════════════════════════════════
    STAGE 2: SEMANTIC POST-CORRECTION USING GEMINI RAG
    ═══════════════════════════════════════════════════════════════════
    
    Perform semantic post-correction on noisy OCR output using Gemini's RAG capabilities.
    This stage interprets, corrects, and structures the raw OCR text into a validated 
    medical record format.
    
    Args:
        raw_text: Noisy OCR output from stage 1 OCR (may contain transcription errors)
        
    Returns:
        BHTExtractedData: Validated and structured medical record data
        
    Raises:
        RuntimeError: If Gemini API is not available
    """
    try:
        if genai is None:
            raise RuntimeError("google.genai is not installed. Please install it with: pip install google-genai")

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        prompt = get_bht_semantic_correction_prompt(raw_text)
        schema = get_bht_extraction_output_schema()

        print("[Gemini] Sending raw OCR text for semantic structuring...")
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            )
        )
        
        # Extract JSON from response text
        response_text = response.text
        if not response_text:
            print("[Gemini ERROR] Empty response from Gemini. Creating fallback data.")
            extracted_data = BHTExtractedData()
            extracted_data.confidence_score = 0.0
            return extracted_data
        
        # Parse JSON response
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"[Gemini ERROR] Failed to parse JSON: {response_text[:200]}")
            extracted_data = BHTExtractedData()
            extracted_data.confidence_score = 0.0
            return extracted_data
        
        # Ensure confidence_score has a valid value
        if 'confidence_score' not in response_json or response_json['confidence_score'] is None:
            response_json['confidence_score'] = 0.5
        
        # Validate and create data model
        extracted_data = BHTExtractedData.model_validate(response_json)
        
        # Store the raw OCR text for reference
        extracted_data.raw_ocr_text = raw_text
        
        # Ensure confidence_score is set
        if extracted_data.confidence_score is None:
            extracted_data.confidence_score = 0.5
        
        print(f"[Gemini] Structuring complete. Confidence: {extracted_data.confidence_score}")
        
        return extracted_data
        
    except Exception as e:
        print(f"[Gemini ERROR] {e}")
        raise e


def extract_image_with_gemini_vision(file) -> BHTExtractedData:
    """
    Direct Gemini vision-based extraction from image (fallback method).
    
    This method uses Gemini's native image understanding to extract structured data
    directly from the medical record image without intermediate OCR.
    
    Args:
        file: UploadFile object containing the BHT image
        
    Returns:
        BHTExtractedData: Extracted and structured medical record data
    """
    try:
        if genai is None:
            raise RuntimeError("google.genai is not installed. Please install it with: pip install google-genai")
        
        # Read file bytes
        file_bytes = file.file.read()
        
        # Determine mime type from file
        mime_type = file.content_type or 'image/jpeg'
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        prompt = """
You are a medical records processing AI assistant. Analyze this BHT (Bed Head Ticket) medical record image carefully.

Extract the following information accurately:
- **Diagnosis**: Primary diagnosis, conditions, or ICD codes
- **Symptoms**: Patient complaints, symptoms, onset, duration, and severity
- **Treatment Plan**: Care instructions, treatment protocols, and management plans
- **Medications**: All prescribed or administered medications with exact dosages, routes (oral, IV, etc.), and frequencies
- **Vitals**: Vital signs including temperature, BP (systolic/diastolic), heart rate, respiratory rate, SpO2, etc.
- **Procedures**: Any medical procedures performed or scheduled
- **Lab Results**: Laboratory test results with values and units (CBC, blood chemistry, etc.)
- **Notes**: Additional clinical observations, progress notes, or provider remarks

Set the confidence_score to reflect how clear and complete the extracted information is (0.0-1.0).

Return ONLY valid JSON. No markdown, no explanations.
""".strip()
        
        schema = get_bht_extraction_output_schema()
        
        print("[Gemini Vision] Extracting from image with direct vision understanding...")
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type,
                ),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            )
        )
        
        # Extract JSON from response
        response_text = response.text
        if not response_text:
            print("[Gemini Vision ERROR] Empty response from Gemini")
            extracted_data = BHTExtractedData()
            extracted_data.confidence_score = 0.0
            return extracted_data
        
        # Parse and validate the response
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"[Gemini Vision ERROR] Failed to parse JSON: {response_text[:200]}")
            extracted_data = BHTExtractedData()
            extracted_data.confidence_score = 0.0
            return extracted_data
        
        # Ensure confidence_score has a valid value
        if 'confidence_score' not in response_json or response_json['confidence_score'] is None:
            response_json['confidence_score'] = 0.5
        
        extracted_data = BHTExtractedData.model_validate(response_json)
        
        # Ensure confidence_score is set
        if extracted_data.confidence_score is None:
            extracted_data.confidence_score = 0.5
        
        print(f"[Gemini Vision] Extraction complete. Confidence: {extracted_data.confidence_score}")
        
        return extracted_data
        
    except Exception as e:
        print(f"[Gemini Vision ERROR] {e}")
        raise e
