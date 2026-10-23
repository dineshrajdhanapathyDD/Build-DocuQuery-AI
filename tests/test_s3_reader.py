"""Mocked unit tests for the `read_s3_document` capability.

All tests here are MOCKED: they use an in-memory FakeS3Client and PDFs built at
runtime. No real AWS calls are made. Live AWS behavior is verified separately
(see README - "Live testing") and is NOT asserted here.

Covered scenarios (as required by the challenge):
  1. Successful retrieval + PDF text extraction
  2. Invalid file type
  3. Missing object
  4. PDF extraction failure (invalid PDF bytes)
  5. Empty PDF (no extractable text)
  6. AWS permission denial
Plus: allow-list enforcement, oversized file, output truncation, encrypted PDF,
and the Strands tool wrapper.
"""

from __future__ import annotations

import json

import pytest

from docuquery import config
from docuquery.s3_reader import read_document
from docuquery.tools import read_s3_document

from .conftest import (
    FakeS3Client,
    make_pdf_bytes,
    make_empty_pdf_bytes,
    make_encrypted_pdf_bytes,
)


# The first catalog entry is our canonical "permitted PDF" for tests.
PERMITTED = config.catalog()[0]
PERMITTED_KEY = PERMITTED.key


# --- 1. Successful retrieval + extraction -----------------------------------
def test_successful_pdf_retrieval(settings):
    pdf = make_pdf_bytes("S3 Standard-IA is for infrequent access.", pages=1)
    client = FakeS3Client({PERMITTED_KEY: pdf})

    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is True
    assert result.error_type == ""
    assert "infrequent access" in result.text
    assert result.pages == 1
    assert "[page 1]" in result.text
    assert result.char_count > 0


def test_multipage_pages_counted(settings):
    pdf = make_pdf_bytes("Reliability pillar note.", pages=3)
    client = FakeS3Client({PERMITTED_KEY: pdf})

    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is True
    assert result.pages == 3
    assert "[page 3]" in result.text


# --- 2. Invalid file type ---------------------------------------------------
def test_invalid_file_type(settings, monkeypatch):
    # Add a permitted-but-unsupported key to the catalog for this test.
    bad = config.CatalogEntry(title="Bad", key="study-docs/notes.docx")
    monkeypatch.setattr(config, "DEFAULT_CATALOG", [bad])

    client = FakeS3Client({bad.key: b"whatever"})
    result = read_document(bad.key, settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "unsupported_type"


# --- 3. Missing object ------------------------------------------------------
def test_missing_object(settings):
    client = FakeS3Client({})  # nothing stored
    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "missing"


# --- 4. PDF extraction failure (invalid PDF) --------------------------------
def test_invalid_pdf(settings):
    client = FakeS3Client({PERMITTED_KEY: b"this is not a pdf at all"})
    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "invalid_pdf"


# --- 5. Empty PDF -----------------------------------------------------------
def test_empty_pdf(settings):
    client = FakeS3Client({PERMITTED_KEY: make_empty_pdf_bytes(pages=1)})
    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "empty"


# --- 6. AWS permission denial -----------------------------------------------
def test_access_denied(settings):
    client = FakeS3Client({PERMITTED_KEY: make_pdf_bytes()})
    client.error_code = "AccessDenied"
    client.error_on = "both"

    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "access_denied"


# --- Allow-list enforcement -------------------------------------------------
def test_unapproved_key_rejected_before_aws(settings):
    client = FakeS3Client({"secret/other.pdf": make_pdf_bytes()})
    result = read_document("secret/other.pdf", settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "not_permitted"


# --- Oversized file ---------------------------------------------------------
def test_oversized_file(settings):
    # settings.max_mb == 1 -> limit is 1 MiB. Build a > 1 MiB PDF.
    big_text = "A" * (1024 * 1024 + 1000)
    pdf = make_pdf_bytes(big_text, pages=1)
    client = FakeS3Client({PERMITTED_KEY: pdf})

    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is False
    assert result.error_type == "oversized"


# --- Output truncation ------------------------------------------------------
def test_output_truncation(settings):
    # settings.max_chars == 500. Create text longer than that (but under size).
    pdf = make_pdf_bytes("B" * 2000, pages=1)
    client = FakeS3Client({PERMITTED_KEY: pdf})

    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is True
    assert result.truncated is True
    assert len(result.text) == settings.max_chars


# --- Encrypted PDF ----------------------------------------------------------
def test_encrypted_pdf(settings):
    client = FakeS3Client({PERMITTED_KEY: make_encrypted_pdf_bytes()})
    result = read_document(PERMITTED_KEY, settings=settings, s3_client=client)

    assert result.ok is False
    # Encrypted blank page may surface as encrypted_pdf or (after failed
    # decrypt) empty; both are handled, non-ok outcomes. Prefer encrypted.
    assert result.error_type in {"encrypted_pdf", "empty"}


# --- Strands tool wrapper ---------------------------------------------------
def test_tool_wrapper_rejects_unknown_title():
    out = json.loads(read_s3_document("No Such Document"))
    assert out["ok"] is False
    assert out["error_type"] == "not_permitted"
