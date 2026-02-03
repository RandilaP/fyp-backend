from typing import Optional, Dict
import io
import os
from pydantic import BaseModel, Field
from typing import List, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

import dotenv

dotenv.load_dotenv()


class BHTExtractedData(BaseModel):
    """Structured data extracted from a BHT (Bed Head Ticket) medical record image."""
    
    diagnosis: Optional[str] = Field(
        description="The primary diagnosis or medical condition identified in the BHT. Include ICD codes if visible."
    )
    symptoms: Optional[str] = Field(
        description="List of symptoms or complaints documented in the BHT. Include onset, duration, and severity if mentioned."
    )
    treatment_plan: Optional[str] = Field(
        description="The treatment plan or care instructions documented in the BHT. Include dosages, frequencies, and durations."
    )
    medications: Optional[str] = Field(
        description="List of medications prescribed or administered. Include drug names, dosages, routes, and frequencies."
    )
    vitals: Optional[Dict] = Field(
        description="Vital signs recorded in the BHT. Should include values like temperature, blood pressure, heart rate, respiratory rate, oxygen saturation, etc."
    )
    procedures: Optional[str] = Field(
        description="Medical procedures performed or planned. Include procedure names, dates, and any relevant details."
    )
    lab_results: Optional[Dict] = Field(
        description="Laboratory test results documented in the BHT. Include test names and their values with units."
    )
    notes: Optional[str] = Field(
        description="Additional clinical notes, observations, or remarks from healthcare providers."
    )


def extract_text_with_gemini(file) -> Optional[BHTExtractedData]:
    """Use Google GenAI (Gemini) to extract structured data from a BHT medical record image.

    This function uses the Gemini API with structured output to extract medical information
    from uploaded BHT (Bed Head Ticket) images and return it as a validated Pydantic model.
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

Important instructions:
1. Extract information EXACTLY as written in the document
2. For vitals and lab results, preserve the numeric values with their units
3. If information is not visible or unclear, leave that field empty
4. Maintain medical terminology and abbreviations as they appear
5. Be thorough - capture all relevant medical information visible in the image
"""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type,
                ),
                prompt
            ],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": BHTExtractedData.model_json_schema(),
            }
        )
        
        # Parse and validate the response using Pydantic
        extracted_data = BHTExtractedData.model_validate_json(response.text)
        return extracted_data
        
    except Exception as e:
        print(f"Error extracting text: {e}")
        raise e
