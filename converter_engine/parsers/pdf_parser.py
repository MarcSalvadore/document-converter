import io
import pdfplumber
from typing import BinaryIO, Any
from markitdown import DocumentConverter, DocumentConverterResult

class LegalPdfConverter(DocumentConverter):
    """
    Custom PDF converter for MarkItDown to prevent justified text from being parsed as tables.
    Forces strict line-based extraction instead of whitespace heuristics.
    """
    
    def accepts(self, file_stream: BinaryIO, stream_info, **kwargs: Any) -> bool:
        ext = (stream_info.extension or "").lower()
        mime = (stream_info.mimetype or "").lower()
        return ext == ".pdf" or mime in ["application/pdf", "application/x-pdf"]

    def convert(self, file_stream: BinaryIO, stream_info, **kwargs: Any) -> DocumentConverterResult:
        from converter_engine.core.ocr_engine import extract_text_from_image
        pdf_bytes_content = file_stream.read()
        pdf_bytes = io.BytesIO(pdf_bytes_content)
        
        TABLE_SETTINGS = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 20,
            "intersection_tolerance": 5,
        }
        
        markdown_chunks = []
        total_text_length = 0
        
        with pdfplumber.open(pdf_bytes) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.find_tables(table_settings=TABLE_SETTINGS)
                extracted_tables = page.extract_tables(table_settings=TABLE_SETTINGS)
                
                items_with_pos = []
                for t, data in zip(tables, extracted_tables):
                    items_with_pos.append((t.bbox[1], t.bbox[3], "table", data))
                
                for img_idx, img in enumerate(page.images, start=1):
                    # Ignore tiny background artifacts
                    if img["bottom"] - img["top"] > 20 and img["x1"] - img["x0"] > 20:
                        items_with_pos.append((img["top"], img["bottom"], "image", (img_idx, img)))
                
                items_with_pos.sort(key=lambda x: x[0])
                
                page_height = page.height
                current_y = 0.0
                page_md = []
                
                for top, bottom, item_type, data in items_with_pos:
                    if top > current_y:
                        crop_box = (0, current_y, page.width, top)
                        try:
                            cropped = page.crop(crop_box)
                            text = cropped.extract_text()
                            if text:
                                page_md.append(text)
                                total_text_length += len(text.strip())
                        except ValueError:
                            pass
                    
                    if item_type == "table":
                        table_md = self._format_table(data)
                        if table_md:
                            page_md.append(table_md)
                            total_text_length += len(table_md)
                    elif item_type == "image":
                        img_idx, img_dict = data
                        crop_box = (img_dict["x0"], img_dict["top"], img_dict["x1"], img_dict["bottom"])
                        try:
                            cropped = page.crop(crop_box)
                            img_obj = cropped.to_image(resolution=300)
                            img_stream = io.BytesIO()
                            img_obj.save(img_stream, format="PNG")
                            img_bytes = img_stream.getvalue()
                            
                            ocr_text = extract_text_from_image(img_bytes)
                            img_md = f"![Page {page_num} Image {img_idx}](image_placeholder)"
                            if ocr_text:
                                img_md += f"\n> **[Image Text Extraction]**\n"
                                for line in ocr_text.splitlines():
                                    if line.strip():
                                        img_md += f"> {line.strip()}\n"
                            page_md.append(img_md)
                        except Exception:
                            pass
                            
                    current_y = bottom
                    
                if current_y < page_height:
                    crop_box = (0, current_y, page.width, page_height)
                    try:
                        cropped = page.crop(crop_box)
                        text = cropped.extract_text()
                        if text:
                            page_md.append(text)
                            total_text_length += len(text.strip())
                    except ValueError:
                        pass
                
                if page_md:
                    markdown_chunks.append("\n\n".join(page_md))
                    
        # Scanned PDF Fallback
        if total_text_length < 100 and len(pdf_bytes_content) > 0:
            markdown_chunks = [] # Clear any sparse artifacts
            with pdfplumber.open(io.BytesIO(pdf_bytes_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        img_obj = page.to_image(resolution=300)
                        img_stream = io.BytesIO()
                        img_obj.save(img_stream, format="PNG")
                        ocr_text = extract_text_from_image(img_stream.getvalue())
                        if ocr_text:
                            markdown_chunks.append(f"<!-- Page {page_num} Scanned Text -->\n" + ocr_text)
                    except Exception:
                        pass

        return DocumentConverterResult(markdown="\n\n---\n\n".join(markdown_chunks))

    def _format_table(self, table_data) -> str:
        if not table_data:
            return ""

        cleaned_rows = []
        for row in table_data:
            cleaned_row = []
            for cell in row:
                cell_text = (cell or "").replace("\n", "<br>").replace("|", "\\|").strip()
                cleaned_row.append(cell_text)
            cleaned_rows.append(cleaned_row)

        if not cleaned_rows:
            return ""

        header_row = cleaned_rows[0]
        col_count = len(header_row)
        if col_count == 0:
            return ""

        separator_row = ["---"] * col_count

        md_lines = [
            "| " + " | ".join(header_row) + " |",
            "| " + " | ".join(separator_row) + " |",
        ]

        for row in cleaned_rows[1:]:
            padded_row = row + [""] * (col_count - len(row))
            md_lines.append("| " + " | ".join(padded_row[:col_count]) + " |")

        return "\n".join(md_lines)
