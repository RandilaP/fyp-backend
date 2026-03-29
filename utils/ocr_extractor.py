"""
OCR EXTRACTION MODULE - Stage 1 of the Hybrid Pipeline

Pure character-level text extraction from medical record images using Gemini Vision.
Returns raw, unstructured OCR output that may contain transcription errors.
"""

import os

import dotenv

dotenv.load_dotenv()

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


def extract_raw_text_with_gemini_ocr(file) -> str:
    """
    ═══════════════════════════════════════════════════════════════════
    STAGE 1: OCR EXTRACTION USING GEMINI VISION
    ═══════════════════════════════════════════════════════════════════
    
    Extract raw text from a BHT medical record image using Gemini Vision OCR.
    This is the first stage of the hybrid pipeline that performs character recognition
    and returns unstructured text for semantic post-correction.
    
    Args:
        file: UploadFile object containing the BHT image
        
    Returns:
        str: Raw OCR text output (may contain transcription errors)
        
    Raises:
        RuntimeError: If Gemini API is not available
    """
    try:
        if genai is None:
            raise RuntimeError("google.genai is not installed. Please install it with: pip install google-genai")

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        file_bytes = file.file.read()
        mime_type = file.content_type or "image/jpeg"

        prompt = (
            "Extract all visible text from this medical record image as plain text. "
            "Preserve line breaks and medical abbreviations exactly as written. "
            "Do not summarize, correct, or structure it. Return text only."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type,
                ),
                prompt,
            ],
        )

        raw_text = (response.text or "").strip()
        if hasattr(file.file, "seek"):
            file.file.seek(0)

        if not raw_text:
            raise RuntimeError("Gemini OCR returned empty text")

        print(f"[Gemini OCR] Raw text extracted. Length: {len(raw_text)} chars")
        return raw_text
    except Exception as e:
        print(f"[Gemini OCR ERROR] {e}")
        raise e
