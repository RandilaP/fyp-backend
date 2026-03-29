"""OCR extraction providers for the BHT hybrid pipeline."""

import os
import io

import dotenv

dotenv.load_dotenv()

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import torch
    from PIL import Image
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
except ImportError:
    torch = None
    Image = None
    TrOCRProcessor = None
    VisionEncoderDecoderModel = None


GEMINI_OCR_MODEL = os.getenv("GEMINI_OCR_MODEL", "gemini-2.5-flash")
TROCR_MODEL = os.getenv("TROCR_MODEL", "microsoft/trocr-base-handwritten")

_trocr_processor = None
_trocr_model = None


def _read_upload_file(file) -> tuple[bytes, str]:
    file_bytes = file.file.read()
    mime_type = file.content_type or "image/jpeg"
    if hasattr(file.file, "seek"):
        file.file.seek(0)
    return file_bytes, mime_type


def _load_trocr_components() -> tuple[TrOCRProcessor, VisionEncoderDecoderModel]:
    global _trocr_processor, _trocr_model

    if TrOCRProcessor is None or VisionEncoderDecoderModel is None or torch is None or Image is None:
        raise RuntimeError(
            "TrOCR dependencies are missing. Install with: pip install torch transformers pillow"
        )

    if _trocr_processor is None or _trocr_model is None:
        _trocr_processor = TrOCRProcessor.from_pretrained(TROCR_MODEL)
        _trocr_model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL)
        _trocr_model.eval()
    return _trocr_processor, _trocr_model


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
        file_bytes, mime_type = _read_upload_file(file)

        prompt = (
            "Extract all visible text from this medical record image as plain text. "
            "Preserve line breaks and medical abbreviations exactly as written. "
            "Do not summarize, correct, or structure it. Return text only."
        )

        response = client.models.generate_content(
            model=GEMINI_OCR_MODEL,
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type,
                ),
                prompt,
            ],
        )

        raw_text = (response.text or "").strip()

        if not raw_text:
            raise RuntimeError("Gemini OCR returned empty text")

        print(f"[Gemini OCR] Raw text extracted. Length: {len(raw_text)} chars")
        return raw_text
    except Exception as e:
        print(f"[Gemini OCR ERROR] {e}")
        raise e


def extract_raw_text_with_trocr(file) -> str:
    """Extract raw text using Microsoft TrOCR."""
    try:
        processor, model = _load_trocr_components()
        file_bytes, _ = _read_upload_file(file)

        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        pixel_values = processor(images=image, return_tensors="pt").pixel_values

        if torch.cuda.is_available():
            model = model.to("cuda")
            pixel_values = pixel_values.to("cuda")
        else:
            model = model.to("cpu")
            pixel_values = pixel_values.to("cpu")

        generated_ids = model.generate(pixel_values, max_new_tokens=768)
        raw_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

        if not raw_text:
            raise RuntimeError("TrOCR returned empty text")

        print(f"[TrOCR] Raw text extracted. Length: {len(raw_text)} chars")
        return raw_text
    except Exception as e:
        print(f"[TrOCR ERROR] {e}")
        raise e
