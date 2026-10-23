"""The `read_s3_document` capability: a safe Amazon S3 -> text reader.

Design goals (mapped to the challenge requirements):

1. Only object keys from the application-controlled catalog are allowed.
2. Objects are fetched with boto3 using the configured region + bucket.
3. File type and size are validated before any processing.
4. PDF text is extracted with pypdf. Plain-text (.txt/.md) is also supported
   and explicitly documented below.
5. Returns extracted text + metadata with an output-length limit.
6. Handles missing objects, invalid/encrypted PDFs, empty docs, oversized
   files, and AWS permission errors - each as a clear, typed result.
7. The model can never pick an arbitrary bucket or unapproved key.
8. No hardcoded credentials - boto3's standard provider chain is used.

The public surface is split in two:
  * `read_document(...)`  - a pure, dependency-injectable function used by both
                            the Strands tool and the unit tests.
  * `read_s3_document`    - the Strands `@tool` wrapper the agent calls.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from . import config
from .config import Settings


# Supported content: PDF via pypdf, plus plain text/markdown read directly.
_PDF_EXTS = (".pdf",)
_TEXT_EXTS = (".txt", ".md")
_ALLOWED_EXTS = _PDF_EXTS + _TEXT_EXTS


@dataclass
class DocumentResult:
    """Structured result returned by the reader.

    `ok` is False for any handled error; `error_type` then names the condition
    so callers (and the agent) can respond appropriately.
    """

    ok: bool
    key: str
    text: str = ""
    pages: int = 0
    char_count: int = 0
    truncated: bool = False
    content_type: str = ""
    size_bytes: int = 0
    error_type: str = ""   # e.g. not_permitted, missing, oversized, ...
    error: str = ""        # human-readable detail

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _make_s3_client(settings: Settings):
    """Create an S3 client using the standard AWS credential provider chain."""
    return boto3.client("s3", region_name=settings.aws_region)


def _extension(key: str) -> str:
    dot = key.rfind(".")
    return key[dot:].lower() if dot != -1 else ""


def _extract_pdf_text(data: bytes) -> tuple[str, int]:
    """Extract text from PDF bytes. Returns (text, page_count).

    Raises ValueError for invalid or encrypted PDFs so the caller can map the
    condition to a typed error result.
    """
    # Imported here so a missing pypdf doesn't break importing the module.
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise ValueError(f"invalid_pdf: {exc}") from exc
    except Exception as exc:  # pypdf can raise assorted parse errors
        raise ValueError(f"invalid_pdf: {exc}") from exc

    if getattr(reader, "is_encrypted", False):
        # Try an empty-password decrypt; if it fails, treat as encrypted.
        try:
            if reader.decrypt("") == 0:  # 0 == failed
                raise ValueError("encrypted_pdf: document is password protected")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"encrypted_pdf: {exc}") from exc

    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            # One bad page shouldn't sink the whole document.
            parts.append("")

    # Join with page markers so the agent can cite page numbers.
    numbered = []
    for i, p in enumerate(parts, start=1):
        p = p.strip()
        if p:
            numbered.append(f"[page {i}]\n{p}")
    text = "\n\n".join(numbered)
    return text, len(reader.pages)


def read_document(
    key: str,
    *,
    settings: Optional[Settings] = None,
    s3_client: Optional[Any] = None,
) -> DocumentResult:
    """Fetch an allow-listed S3 object and return extracted text + metadata.

    Args:
        key: S3 object key. MUST be present in the application catalog.
        settings: Optional Settings override (tests inject their own).
        s3_client: Optional preconstructed boto3 S3 client (tests inject a mock).

    Returns:
        DocumentResult - `ok=True` on success, otherwise `ok=False` with a
        populated `error_type` (one of: not_permitted, unsupported_type,
        oversized, missing, access_denied, empty, invalid_pdf, encrypted_pdf,
        aws_error).
    """
    settings = settings or config.settings

    # (7) Enforce the allow-list BEFORE touching AWS.
    if not config.is_permitted_key(key):
        return DocumentResult(
            ok=False,
            key=key,
            error_type="not_permitted",
            error="Requested key is not in the approved document catalog.",
        )

    # (3) Validate the file type up front.
    ext = _extension(key)
    if ext not in _ALLOWED_EXTS:
        return DocumentResult(
            ok=False,
            key=key,
            error_type="unsupported_type",
            error=f"Unsupported file type '{ext}'. Allowed: {', '.join(_ALLOWED_EXTS)}.",
        )

    client = s3_client or _make_s3_client(settings)
    bucket = settings.bucket

    # Size pre-check via HEAD so we don't download an oversized object.
    try:
        head = client.head_object(Bucket=bucket, Key=key)
        size = int(head.get("ContentLength", 0))
        if size > settings.max_bytes:
            return DocumentResult(
                ok=False,
                key=key,
                size_bytes=size,
                error_type="oversized",
                error=(
                    f"Document is {size} bytes, exceeding the "
                    f"{settings.max_bytes}-byte limit."
                ),
            )
    except ClientError as exc:
        return _map_client_error(exc, key)
    except BotoCoreError as exc:
        return DocumentResult(
            ok=False, key=key, error_type="aws_error", error=str(exc)
        )

    # Download the object body.
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
        content_type = obj.get("ContentType", "")
    except ClientError as exc:
        return _map_client_error(exc, key)
    except BotoCoreError as exc:
        return DocumentResult(
            ok=False, key=key, error_type="aws_error", error=str(exc)
        )

    # Re-check actual size after download (HEAD can be stale/absent in mocks).
    if len(body) > settings.max_bytes:
        return DocumentResult(
            ok=False,
            key=key,
            size_bytes=len(body),
            error_type="oversized",
            error=(
                f"Document is {len(body)} bytes, exceeding the "
                f"{settings.max_bytes}-byte limit."
            ),
        )

    # (4) Extract text by type.
    pages = 0
    if ext in _PDF_EXTS:
        try:
            text, pages = _extract_pdf_text(body)
        except ValueError as exc:
            msg = str(exc)
            etype = "encrypted_pdf" if msg.startswith("encrypted_pdf") else "invalid_pdf"
            return DocumentResult(
                ok=False,
                key=key,
                size_bytes=len(body),
                content_type=content_type,
                error_type=etype,
                error=msg,
            )
    else:  # plain text / markdown
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - decode with replace won't raise
            return DocumentResult(
                ok=False, key=key, error_type="invalid_pdf", error=str(exc)
            )

    # (6) Empty-document check.
    if not text.strip():
        return DocumentResult(
            ok=False,
            key=key,
            pages=pages,
            size_bytes=len(body),
            content_type=content_type,
            error_type="empty",
            error="No extractable text found in the document.",
        )

    # (5) Enforce output-length limit.
    truncated = False
    if len(text) > settings.max_chars:
        text = text[: settings.max_chars]
        truncated = True

    return DocumentResult(
        ok=True,
        key=key,
        text=text,
        pages=pages,
        char_count=len(text),
        truncated=truncated,
        content_type=content_type,
        size_bytes=len(body),
    )


def _map_client_error(exc: ClientError, key: str) -> DocumentResult:
    """Translate a boto3 ClientError into a typed DocumentResult."""
    code = exc.response.get("Error", {}).get("Code", "")
    if code in {"NoSuchKey", "404", "NotFound"}:
        return DocumentResult(
            ok=False, key=key, error_type="missing",
            error="The requested object does not exist.",
        )
    if code in {"AccessDenied", "403", "AllAccessDisabled"}:
        return DocumentResult(
            ok=False, key=key, error_type="access_denied",
            error="Access denied by AWS - check IAM permissions for this key.",
        )
    if code in {"NoSuchBucket"}:
        return DocumentResult(
            ok=False, key=key, error_type="aws_error",
            error="The configured bucket does not exist.",
        )
    return DocumentResult(
        ok=False, key=key, error_type="aws_error",
        error=f"AWS error [{code}]: {exc}",
    )
