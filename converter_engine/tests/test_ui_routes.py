"""Unit tests for Web UI route, static file serving, and direct file download endpoints."""

from fastapi.testclient import TestClient
from converter_engine.api.main import app
from converter_engine.tests.conftest import sample_docx

client = TestClient(app)


def test_serve_index_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Doc-to-Markdown" in response.text
    assert "Drag & Drop your document here" in response.text


def test_static_asset_serving():
    response = client.get("/static/index.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Document to Markdown Converter" in response.text


def test_convert_download_endpoint(sample_docx):
    with open(sample_docx, "rb") as f:
        response = client.post(
            "/v1/convert?download=true",
            files=[("files", ("synthetic_sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
        )

    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "attachment; filename=\"synthetic_sample.md\"" in response.headers["content-disposition"]
    assert "# Synthetic Document Title" in response.text


def test_convert_file_endpoint(sample_docx):
    with open(sample_docx, "rb") as f:
        response = client.post(
            "/v1/convert/file",
            files=[("files", ("synthetic_sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
        )

    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "attachment; filename=\"synthetic_sample.md\"" in response.headers["content-disposition"]
    assert "# Synthetic Document Title" in response.text
