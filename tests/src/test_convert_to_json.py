"""Tests for the /convert_to_json endpoint.

converter.convert_to_json is patched for all tests so the suite runs
without docling installed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PDF_BYTES = b"%PDF-1.4 stub"
_HEADERS = {"Content-Type": "application/octet-stream"}
_SAMPLE_DOC = {"name": "report", "pages": [{"page_no": 1}]}


# ---------------------------------------------------------------------------
# POST /convert_to_json/ — validation
# ---------------------------------------------------------------------------

def test_unsupported_extension_returns_415(client: TestClient) -> None:
    response = client.post(
        "/convert_to_json/?filename=report.xyz",
        content=_PDF_BYTES,
        headers=_HEADERS,
    )
    assert response.status_code == 415


def test_missing_filename_returns_422(client: TestClient) -> None:
    response = client.post("/convert_to_json/", content=_PDF_BYTES, headers=_HEADERS)
    assert response.status_code == 422


def test_batch_size_zero_returns_422(client: TestClient) -> None:
    response = client.post(
        "/convert_to_json/?filename=report.pdf&page_batch_size=0",
        content=_PDF_BYTES,
        headers=_HEADERS,
    )
    assert response.status_code == 422


def test_batch_size_over_max_returns_422(client: TestClient) -> None:
    response = client.post(
        "/convert_to_json/?filename=report.pdf&page_batch_size=999",
        content=_PDF_BYTES,
        headers=_HEADERS,
    )
    assert response.status_code == 422


def test_file_too_large_returns_413(client: TestClient) -> None:
    from app.config import settings

    oversized = b"x" * (settings.max_file_size_mb * 1024 * 1024 + 1)
    response = client.post(
        "/convert_to_json/?filename=big.pdf",
        content=oversized,
        headers=_HEADERS,
    )
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# POST /convert_to_json/ — JSON response
# ---------------------------------------------------------------------------

@patch("app.routers.convert_to_json.converter.convert_to_json", new_callable=AsyncMock)
def test_returns_json(mock_convert, client: TestClient) -> None:
    mock_convert.return_value = _SAMPLE_DOC

    response = client.post(
        "/convert_to_json/?filename=report.pdf",
        content=_PDF_BYTES,
        headers=_HEADERS,
    )

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert response.json() == _SAMPLE_DOC


@patch("app.routers.convert_to_json.converter.convert_to_json", new_callable=AsyncMock)
def test_x_filename_header_present(mock_convert, client: TestClient) -> None:
    mock_convert.return_value = _SAMPLE_DOC

    response = client.post(
        "/convert_to_json/?filename=annual-report.pdf",
        content=_PDF_BYTES,
        headers=_HEADERS,
    )

    assert response.headers.get("x-filename") == "annual-report.pdf"


@patch("app.routers.convert_to_json.converter.convert_to_json", new_callable=AsyncMock)
def test_batch_size_forwarded_to_converter(mock_convert, client: TestClient) -> None:
    mock_convert.return_value = _SAMPLE_DOC

    client.post(
        "/convert_to_json/?filename=report.pdf&page_batch_size=4",
        content=_PDF_BYTES,
        headers=_HEADERS,
    )

    args, kwargs = mock_convert.call_args
    actual_batch = kwargs.get("page_batch_size", args[2] if len(args) > 2 else None)
    assert actual_batch == 4


@patch("app.routers.convert_to_json.converter.convert_to_json", new_callable=AsyncMock)
def test_docx_is_accepted(mock_convert, client: TestClient) -> None:
    mock_convert.return_value = _SAMPLE_DOC

    response = client.post(
        "/convert_to_json/?filename=doc.docx",
        content=b"PK stub",
        headers=_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == _SAMPLE_DOC


@patch("app.routers.convert_to_json.converter.convert_to_json", new_callable=AsyncMock)
def test_image_png_is_accepted(mock_convert, client: TestClient) -> None:
    mock_convert.return_value = _SAMPLE_DOC

    response = client.post(
        "/convert_to_json/?filename=scan.png",
        content=b"\x89PNG stub",
        headers=_HEADERS,
    )

    assert response.status_code == 200
