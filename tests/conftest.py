"""Shared test fixtures and fakes.

Everything here is MOCKED - no network or real AWS calls are made. These tests
exercise the reader's logic and error handling against an in-memory fake S3
client and small PDFs generated at runtime.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pytest
from botocore.exceptions import ClientError

from docuquery.config import Settings


# ---------------------------------------------------------------------------
# Tiny PDF builders (pure pypdf, no fixture files on disk)
# ---------------------------------------------------------------------------
def make_pdf_bytes(text: str = "Hello S3 document.", pages: int = 1) -> bytes:
    """Create a minimal valid PDF containing `text` on each of `pages` pages.

    Hand-builds a tiny PDF with a proper cross-reference table and `startxref`
    trailer so that pypdf's `extract_text()` returns the string. Avoids a
    reportlab dependency.
    """
    # Escape characters that are special inside a PDF string literal.
    safe = (
        text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    ).encode("latin-1", "replace")

    # Build object bodies (object numbers 1..N). We track each object's byte
    # offset from the start of the file to emit a correct xref table.
    header = b"%PDF-1.4\n"
    objects: list[bytes] = []  # each already terminated with "endobj\n"

    page_obj_nums: list[int] = []
    # Object numbering: 1 = Catalog, 2 = Pages, then (Page, Content) per page.
    next_num = 3
    page_chunks: list[bytes] = []
    for _ in range(pages):
        page_num = next_num
        content_num = next_num + 1
        next_num += 2
        page_obj_nums.append(page_num)

        stream = b"BT /F1 18 Tf 50 150 Td (" + safe + b") Tj ET"
        page_chunks.append(
            (
                f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 200 200] /Contents {content_num} 0 R "
                f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 "
                f"/BaseFont /Helvetica >> >> >> >>\nendobj\n"
            ).encode()
        )
        page_chunks.append(
            f"{content_num} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream\nendobj\n"
        )

    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(
        (
            f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {pages} >>\nendobj\n"
        ).encode()
    )
    objects.extend(page_chunks)

    total_objs = 2 + 2 * pages

    # Assemble the body while recording offsets.
    out = bytearray(header)
    offsets: list[int] = [0] * (total_objs + 1)  # 1-indexed; [0] is the free obj
    for i, obj in enumerate(objects, start=1):
        offsets[i] = len(out)
        out.extend(obj)

    xref_start = len(out)
    out.extend(f"xref\n0 {total_objs + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")  # free object 0
    for i in range(1, total_objs + 1):
        out.extend(f"{offsets[i]:010d} 00000 n \n".encode())

    out.extend(
        (
            f"trailer\n<< /Size {total_objs + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode()
    )
    return bytes(out)


def make_empty_pdf_bytes(pages: int = 1) -> bytes:
    """Create a valid PDF with blank pages (no extractable text)."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_encrypted_pdf_bytes(password: str = "secret") -> bytes:
    """Create a password-encrypted PDF."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fake S3 client
# ---------------------------------------------------------------------------
@dataclass
class _Body:
    data: bytes

    def read(self) -> bytes:
        return self.data


class FakeS3Client:
    """Minimal stand-in for a boto3 S3 client used by the reader.

    Configure it with a dict of {key: bytes} for stored objects, plus optional
    error injection for head/get operations.
    """

    def __init__(self, objects: dict[str, bytes] | None = None):
        self.objects: dict[str, bytes] = objects or {}
        self.error_code: str | None = None       # inject a ClientError code
        self.error_on: str = "get"               # "get" or "head" or "both"

    def _maybe_error(self, op: str):
        if self.error_code and self.error_on in (op, "both"):
            raise ClientError(
                {"Error": {"Code": self.error_code, "Message": "injected"}},
                operation_name=op,
            )

    def head_object(self, Bucket: str, Key: str):  # noqa: N803 - boto3 style
        self._maybe_error("head")
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "not found"}},
                operation_name="HeadObject",
            )
        return {"ContentLength": len(self.objects[Key]), "ContentType": "application/pdf"}

    def get_object(self, Bucket: str, Key: str):  # noqa: N803
        self._maybe_error("get")
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
                operation_name="GetObject",
            )
        return {"Body": _Body(self.objects[Key]), "ContentType": "application/pdf"}


@pytest.fixture
def settings() -> Settings:
    """Deterministic settings for tests (small limits, test bucket)."""
    s = Settings()
    s.bucket = "test-bucket"
    s.aws_region = "us-east-1"
    s.max_mb = 1
    s.max_chars = 500
    return s
