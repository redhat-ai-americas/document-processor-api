"""Integration tests that POST each sample file to a running local service.

Requires the service to be running before executing. Configure the base URL via
the SERVICE_URL environment variable (default: http://localhost:8080).

Run with:
    SERVICE_URL=http://localhost:8080 pytest tests/src/test_integration_samples.py -v
"""

import json
import os
import re
from pathlib import Path

import pytest
import requests

_MIN_CHARS = 500
_MIN_LINES = 5
_MD_PATTERNS = re.compile(r"(^#{1,6} |\*\*|__|^\s*[-*+] |\[.+\]\(.+\)|^```)", re.MULTILINE)


def _assert_markdown_body(body: str) -> None:
    assert len(body) >= _MIN_CHARS, f"Body too short: {len(body)} chars (expected >= {_MIN_CHARS})"
    lines = [l for l in body.splitlines() if l.strip()]
    assert len(lines) >= _MIN_LINES, f"Too few lines: {len(lines)} (expected >= {_MIN_LINES})"
    assert _MD_PATTERNS.search(body), "Body does not appear to contain Markdown formatting"

def _assert_json_body(body: str) -> None:
    try:
        doc = json.loads(body)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Response is not valid JSON: {exc}")

    assert isinstance(doc, dict), "JSON body must be an object"
    assert doc.get("schema_name") == "DoclingDocument", (
        f"Expected schema_name 'DoclingDocument', got {doc.get('schema_name')!r}"
    )
    assert "version" in doc, "Missing 'version' field"
    assert "name" in doc, "Missing 'name' field"
    assert "pages" in doc, "Missing 'pages' field"
    assert isinstance(doc["pages"], dict), "'pages' must be an object"
    assert len(doc["pages"]) > 0, "Document contains no pages"

SAMPLES_DIR = Path(__file__).parents[2] / "samples"
TARGET_DIR = Path(__file__).parents[2] / "target"
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:8080")

SAMPLE_FILES = sorted(SAMPLES_DIR.glob("*"))


def _convert_url(route: str = "convert_to_md", endpoint: str = "") -> str:
    base = f"{SERVICE_URL}/{route}"
    return f"{base}/{endpoint}" if endpoint else f"{base}/"


@pytest.fixture(scope="module", autouse=True)
def require_service() -> None:
    try:
        resp = requests.get(f"{SERVICE_URL}/health", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Service not reachable at {SERVICE_URL}: {exc}")


@pytest.mark.parametrize("sample", SAMPLE_FILES, ids=lambda p: p.name)
def test_convert_to_md_using_sample(sample: Path) -> None:
    data = sample.read_bytes()
    resp = requests.post(
        _convert_url(),
        params={"filename": sample.name},
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        stream=True,
        timeout=900,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    assert "text/plain" in resp.headers.get("content-type", "")
    assert resp.headers.get("x-filename") == sample.name

    body = resp.text
    TARGET_DIR.mkdir(exist_ok=True)
    (TARGET_DIR / sample.with_suffix(".md").name).write_text(body, encoding="utf-8")
    _assert_markdown_body(body)


@pytest.mark.parametrize("sample", SAMPLE_FILES, ids=lambda p: p.name)
def test_convert_to_json_using_sample(sample: Path) -> None:
    data = sample.read_bytes()
    resp = requests.post(
        _convert_url("convert_to_json"),
        params={"filename": sample.name},
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        stream=True,
        timeout=900,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    assert "application/json" in resp.headers.get("content-type", "")
    assert resp.headers.get("x-filename") == sample.name

    body = resp.text
    TARGET_DIR.mkdir(exist_ok=True)
    (TARGET_DIR / sample.with_suffix(".json").name).write_text(body, encoding="utf-8")
    _assert_json_body(body)
