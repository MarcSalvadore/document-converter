"""Integration test for FastAPI REST API endpoints using Starlette TestClient."""

import os
import sys
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from converter_engine.api.main import app
from converter_engine.test_converter import (
    create_sample_docx,
    create_sample_pptx,
    create_sample_pdf,
)

client = TestClient(app)


def test_api_endpoints():
    print("--- Testing GET /health ---")
    response = client.get("/health")
    assert response.status_code == 200, f"Health check failed: {response.text}"
    data = response.json()
    print(f"Health check response: {data}")
    assert data["status"] == "healthy"
    assert "version" in data
    print("GET /health PASSED!\n")

    # Create temporary sample files
    test_dir = os.path.join(os.path.dirname(__file__), "test_files")
    os.makedirs(test_dir, exist_ok=True)

    docx_path = os.path.join(test_dir, "sample.docx")
    pptx_path = os.path.join(test_dir, "sample.pptx")
    pdf_path = os.path.join(test_dir, "sample.pdf")

    create_sample_docx(docx_path)
    create_sample_pptx(pptx_path)
    create_sample_pdf(pdf_path)

    print("--- Testing POST /v1/convert (DOCX) ---")
    with open(docx_path, "rb") as f:
        response = client.post(
            "/v1/convert",
            files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert response.status_code == 200, f"DOCX convert failed: {response.text}"
    res_data = response.json()
    print(f"DOCX Filename: {res_data['filename']}")
    assert "# Sample Document Title" in res_data["markdown"]
    print("DOCX API conversion PASSED!\n")

    print("--- Testing POST /v1/convert (PPTX) ---")
    with open(pptx_path, "rb") as f:
        response = client.post(
            "/v1/convert",
            files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
    assert response.status_code == 200, f"PPTX convert failed: {response.text}"
    res_data = response.json()
    print(f"PPTX Filename: {res_data['filename']}")
    assert "Slide 1: Introduction Slide" in res_data["markdown"]
    print("PPTX API conversion PASSED!\n")

    print("--- Testing POST /v1/convert (PDF) ---")
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/v1/convert",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200, f"PDF convert failed: {response.text}"
    res_data = response.json()
    print(f"PDF Filename: {res_data['filename']}")
    assert "PDF Document Title" in res_data["markdown"]
    print("PDF API conversion PASSED!\n")

    print("--- Testing POST /v1/convert (Invalid File Extension) ---")
    response = client.post(
        "/v1/convert",
        files={"file": ("test.txt", b"Hello world", "text/plain")},
    )
    assert response.status_code == 400, f"Expected 400 Bad Request, got {response.status_code}"
    print(f"Invalid extension response: {response.json()}")
    print("Invalid File Extension test PASSED!\n")

    print("ALL FASTAPI REST API TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_api_endpoints()
