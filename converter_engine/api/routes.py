"""API Endpoints for Document to Markdown Conversion and System Health."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response

from converter_engine.core.router import DocumentRouter

router = APIRouter()
START_TIME = time.time()

ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}


@router.get("/health", summary="Health Check", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Return health status, version, and uptime metadata."""
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds,
        "supported_formats": ["docx", "pptx", "pdf"],
    }


@router.post(
    "/v1/convert",
    summary="Convert Document to Markdown",
    tags=["Conversion"],
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/convert",
    summary="Convert Document to Markdown (Alias)",
    tags=["Conversion"],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def convert_document(
    files: List[UploadFile] = File(...),
    download: bool = Query(False, description="If true, returns direct .md file attachment response for the first successful file"),
):
    """Accept multipart document upload (DOCX, PPTX, PDF) and return Markdown content or file download.

    Args:
        files: List of multipart file objects.
        download: Optional query parameter to return attachment response for the first file.

    Returns:
        JSON response with markdown string, OR direct Response attachment.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )

    results = []

    for file in files:
        if not file.filename:
            results.append({"filename": "unknown", "status": "error", "error": "Uploaded file must have a valid filename."})
            continue

        # Validate file extension
        ext = ""
        if "." in file.filename:
            ext = f".{file.filename.rsplit('.', 1)[-1].lower()}"

        if ext not in ALLOWED_EXTENSIONS:
            results.append({"filename": file.filename, "status": "error", "error": f"Unsupported file extension '{ext}'. Allowed extensions: {sorted(list(ALLOWED_EXTENSIONS))}"})
            continue

        try:
            await file.seek(0)
            raw_bytes = await file.read()
            if not raw_bytes:
                results.append({"filename": file.filename, "status": "error", "error": "Uploaded file payload is empty."})
                continue

            document_router = DocumentRouter()
            parsed_result = await asyncio.to_thread(
                document_router.convert_bytes,
                raw_bytes,
                file.filename,
            )

            # Base64 encode images
            images_b64 = {}
            if hasattr(parsed_result, "images"):
                import base64
                for name, bytes_data in parsed_result.images.items():
                    images_b64[name] = base64.b64encode(bytes_data).decode("utf-8")

            results.append({
                "filename": file.filename,
                "status": "success",
                "markdown": parsed_result.markdown if hasattr(parsed_result, "markdown") else parsed_result,
                "images": images_b64,
            })

        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e),
            })
        finally:
            await file.close()

    if download:
        # Backward compatibility for direct file download
        for res in results:
            if res["status"] == "success":
                derived_name = res["filename"].rsplit('.', 1)[0] if '.' in res["filename"] else res["filename"]
                md_filename = f"{derived_name}.md"

                if res.get("images"):
                    import io
                    import zipfile
                    import base64
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        zip_file.writestr(md_filename, res["markdown"])
                        for img_name, img_b64 in res["images"].items():
                            zip_file.writestr(img_name, base64.b64decode(img_b64))
                            
                    return Response(
                        content=zip_buffer.getvalue(),
                        media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{derived_name}_with_assets.zip"'},
                    )
                else:
                    return Response(
                        content=res["markdown"],
                        media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{md_filename}"'},
                    )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were successfully converted for download.",
        )

    return {"results": results}


@router.post(
    "/v1/convert/file",
    summary="Convert Document and Return File Attachment",
    tags=["Conversion"],
    status_code=status.HTTP_200_OK,
)
async def convert_document_to_file(files: List[UploadFile] = File(...)):
    """Accept multipart document upload and return direct .md file attachment for the first file."""
    return await convert_document(files=files, download=True)


# --- Masking Endpoints ---
import os
import tempfile
import zipfile
import io
from fastapi import Form
from converter_engine.masking.docx_masker import redact_docx
from converter_engine.masking.spreadsheet_masker import redact_xlsx, redact_csv
from converter_engine.masking.pdf_masker import redact_pdf

MASKING_ALLOWED_EXTENSIONS = {".docx", ".xlsx", ".csv", ".pdf"}

@router.post(
    "/v1/mask",
    summary="Data Masking / Redaction for Documents",
    tags=["Masking"],
    status_code=status.HTTP_200_OK,
)
async def mask_documents(
    files: List[UploadFile] = File(...),
    dry_run: bool = Form(False),
    company_list: Optional[str] = Form(None),
    detect_company_auto: bool = Form(True),
    detect_npwp: bool = Form(True),
    detect_rekening: bool = Form(True),
    detect_address: bool = Form(True),
):
    """Data Masking API for documents."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded.")

    company_names = [name.strip() for name in company_list.split("\n") if name.strip()] if company_list else []
    detect_opts = {
        "detect_company_auto": detect_company_auto,
        "detect_npwp": detect_npwp,
        "detect_rekening": detect_rekening,
        "detect_address": detect_address,
    }

    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_files = []
        
        for file in files:
            if not file.filename:
                continue
                
            ext = f".{file.filename.rsplit('.', 1)[-1].lower()}" if "." in file.filename else ""
            if ext not in MASKING_ALLOWED_EXTENSIONS:
                results.append({"filename": file.filename, "status": "error", "error": f"Unsupported extension {ext}"})
                continue
                
            input_path = os.path.join(temp_dir, f"in_{file.filename}")
            output_path = os.path.join(temp_dir, f"out_{file.filename}")
            
            # Save uploaded file
            with open(input_path, "wb") as f:
                f.write(await file.read())
            
            try:
                def run_masker():
                    if ext == ".docx":
                        return redact_docx(input_path, output_path, company_names=company_names, **detect_opts)
                    elif ext == ".xlsx":
                        return redact_xlsx(input_path, output_path, company_names=company_names, **detect_opts)
                    elif ext == ".csv":
                        return redact_csv(input_path, output_path, company_names=company_names, **detect_opts)
                    elif ext == ".pdf":
                        return redact_pdf(input_path, output_path, company_names=company_names, **detect_opts)
                    return []
                
                log = await asyncio.to_thread(run_masker)
                
                if dry_run:
                    # Filter and format logs for UI
                    formatted_matches = []
                    for entry in log:
                        formatted_matches.append({
                            "location": entry.get("lokasi", "N/A"),
                            "label": entry.get("label", "N/A"),
                            "text": entry.get("teks_asli", "N/A")
                        })
                    results.append({"filename": file.filename, "status": "success", "matches": formatted_matches})
                else:
                    output_files.append((file.filename, output_path))
                    results.append({"filename": file.filename, "status": "success"})
                    
            except Exception as e:
                results.append({"filename": file.filename, "status": "error", "error": str(e)})
                
        if dry_run:
            return {"results": results}
        
        # If not dry_run, return file or zip
        if not output_files:
            raise HTTPException(status_code=400, detail="No files successfully processed.")
            
        if len(output_files) == 1:
            # Single file download
            orig_name, out_path = output_files[0]
            with open(out_path, "rb") as f:
                file_bytes = f.read()
            return Response(
                content=file_bytes,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="redacted_{orig_name}"'}
            )
        else:
            # Multiple files zip download
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for orig_name, out_path in output_files:
                    zip_file.write(out_path, arcname=f"redacted_{orig_name}")
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="redacted_documents.zip"'}
            )
