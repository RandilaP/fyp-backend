from typing import Optional
from google import genai
import io
import os

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None


def extract_text_with_gemini(file_bytes: bytes) -> Optional[str]:
    """Use Google GenAI (Gemini) to extract text from an image. If not available, fall back to pytesseract.

    This function keeps the implementation minimal: it sends the image bytes to genai with a text-extraction
    instruction and returns the result. Replace with a more advanced pipeline as needed.
    """
    # Prefer Gemeni via google.genai if configured
    try:
        client = genai.Client()
        # Use the images.generate or embeddings API depending on SDK; keep a simple prompt approach
        response = client.send(
            {
                "input": [
                    {
                        "type": "image",
                        "image": {"bytes": file_bytes},
                    },
                    {
                        "type": "text",
                        "text": "Extract the visible text from the image as plain text."
                    }
                ]
            }
        )
        # If response has textual output, return it; this depends on the genai client response structure
        if hasattr(response, "output"):
            # try to coalesce text
            parts = []
            for out in response.output:
                text = getattr(out, "text", None)
                if text:
                    parts.append(text)
            if parts:
                return "\n".join(parts)
        # fallback: try str()
        return str(response)
    except Exception:
        # fallback to pytesseract if available
        if pytesseract and Image:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                return pytesseract.image_to_string(img)
            except Exception:
                return None
        return None
