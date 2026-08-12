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
            markdown_output = await asyncio.to_thread(
                document_router.convert_bytes,
                raw_bytes,
                file.filename,
            )

            results.append({
                "filename": file.filename,
                "status": "success",
                "markdown": markdown_output,
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
