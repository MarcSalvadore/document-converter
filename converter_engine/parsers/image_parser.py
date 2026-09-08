from typing import BinaryIO, Any
from markitdown import DocumentConverter, DocumentConverterResult
from converter_engine.core.ocr_engine import extract_text_from_image

class ImageParser(DocumentConverter):
    """
    Custom MarkItDown plugin to handle standalone image files using offline OCR.
    """
    def accepts(self, file_stream: BinaryIO, stream_info, **kwargs: Any) -> bool:
        ext = (stream_info.extension or "").lower()
        mime = (stream_info.mimetype or "").lower()
        return ext in [".png", ".jpg", ".jpeg"] or "image" in mime

    def convert(self, file_stream: BinaryIO, stream_info, **kwargs: Any) -> DocumentConverterResult:
        image_bytes = file_stream.read()
        ocr_text = extract_text_from_image(image_bytes)
        
        md_content = "# Image OCR Extraction\n\n"
        if ocr_text:
            md_content += f"> **[Image Text Extraction]**\n"
            for line in ocr_text.splitlines():
                if line.strip():
                    md_content += f"> {line.strip()}\n"
        else:
            md_content += "_No text detected in image._\n"
            
        return DocumentConverterResult(markdown=md_content.strip())
