"""API Endpoints for Document to Markdown Conversion and System Health."""

import time
from typing import Dict, Any, Optional
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
    file: UploadFile = File(...),
    download: bool = Query(False, description="If true, returns direct .md file attachment response"),
):
    """Accept multipart document upload (DOCX, PPTX, PDF) and return Markdown content or file download.

    Args:
        file: Multipart file object.
        download: Optional query parameter to return attachment response.

    Returns:
        JSON response with markdown string, OR direct Response attachment.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    # Validate file extension
    ext = ""
    if "." in file.filename:
        ext = f".{file.filename.rsplit('.', 1)[-1].lower()}"

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file extension '{ext}'. "
                f"Allowed extensions: {sorted(list(ALLOWED_EXTENSIONS))}"
            ),
        )

    try:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file payload is empty.",
            )

        document_router = DocumentRouter()
        markdown_output = document_router.convert_bytes(
            file_bytes=raw_bytes,
            filename=file.filename,
        )

        derived_name = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
        md_filename = f"{derived_name}.md"

        if download:
            return Response(
                content=markdown_output,
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{md_filename}"'},
            )

        return {
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "markdown": markdown_output,
        }

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except FileNotFoundError as fnfe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(fnfe),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during document conversion: {str(e)}",
        )


@router.post(
    "/v1/convert/file",
    summary="Convert Document and Return File Attachment",
    tags=["Conversion"],
    status_code=status.HTTP_200_OK,
)
async def convert_document_to_file(file: UploadFile = File(...)):
    """Accept multipart document upload and return direct .md file attachment."""
    return await convert_document(file=file, download=True)
