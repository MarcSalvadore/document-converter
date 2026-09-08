import io
from PIL import Image
import pytesseract

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extracts text from an image using Tesseract OCR.
    Safely degrades and returns an empty string if Tesseract binaries are not installed.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if not already
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
            
        # Execute OCR supporting Indonesian and English
        text = pytesseract.image_to_string(img, lang="ind+eng")
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        # Graceful degradation if OCR binaries are missing
        return ""
    except Exception as e:
        # Handle invalid images or other errors gracefully
        return ""
