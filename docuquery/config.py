"""Central configuration for DocuQuery AI.

All security-relevant settings live here so the agent/model can never widen its
own access. The model receives only a *list of permitted document keys*; it
cannot name an arbitrary bucket or an unapproved object key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

try:
    # Load a local .env if present. Safe no-op when the package isn't installed.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


# Keys that may be supplied via Streamlit Community Cloud "Secrets" (TOML).
# On Cloud there is no .env and no IAM role, so both configuration AND AWS
# credentials arrive through st.secrets. We copy them into os.environ (without
# overwriting anything already set) so the rest of this module - and boto3's
# standard provider chain - pick them up unchanged. This import is wrapped so
# tests and CLI usage never require Streamlit.
_SECRET_KEYS = (
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "DOCUQUERY_BUCKET",
    "DOCUQUERY_PREFIX",
    "BEDROCK_MODEL_ID",
    "DOCUQUERY_MAX_MB",
    "DOCUQUERY_MAX_CHARS",
)


def _load_streamlit_secrets() -> None:
    """Bridge st.secrets -> os.environ when running under Streamlit.

    No-op if Streamlit isn't installed or no secrets file is configured.
    Never overwrites a value already present in the environment, so a local
    .env or real shell credentials always win.
    """
    try:
        import streamlit as st  # noqa: WPS433 - optional, UI-only dependency
    except Exception:
        return
    try:
        # Accessing st.secrets with no secrets.toml raises; guard it.
        available = dict(st.secrets)
    except Exception:
        return
    for key in _SECRET_KEYS:
        if key in available and os.environ.get(key) in (None, ""):
            os.environ[key] = str(available[key])


_load_streamlit_secrets()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Runtime settings, resolved from environment variables with safe defaults."""

    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    bucket: str = field(default_factory=lambda: os.getenv("DOCUQUERY_BUCKET", ""))
    prefix: str = field(default_factory=lambda: os.getenv("DOCUQUERY_PREFIX", ""))
    model_id: str = field(
        default_factory=lambda: os.getenv(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
        )
    )
    max_mb: int = field(default_factory=lambda: int(os.getenv("DOCUQUERY_MAX_MB", "50")))
    max_chars: int = field(
        default_factory=lambda: int(os.getenv("DOCUQUERY_MAX_CHARS", "12000"))
    )

    @property
    def max_bytes(self) -> int:
        return self.max_mb * 1024 * 1024


# A module-level singleton is convenient for the app; tests construct their own.
settings = Settings()


# ---------------------------------------------------------------------------
# Application-controlled document catalog (the allow-list).
#
# This is the ONLY set of object keys the agent is permitted to read. The model
# selects a document by its human-friendly title; the title maps to a key here.
# Keys are validated against this catalog before any S3 call is made.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogEntry:
    title: str          # Shown in the UI and to the model.
    key: str            # S3 object key (relative to bucket).
    description: str = ""  # Optional human description.


# Default demo catalog. Edit these entries (or the keys) to match your bucket.
# The `.pdf` files are expected to exist under DOCUQUERY_PREFIX in your bucket.
#
# For this deployment only the first entry is uploaded (see
# scripts/make_sample_pdf.py --upload). Add the other documents to your bucket
# before enabling their catalog entries.
DEFAULT_CATALOG: List[CatalogEntry] = [
    CatalogEntry(
        title="AWS Solutions Architect Study Notes (personal)",
        key="study-docs/saa-personal-notes.pdf",
        description="Private exam-prep notes - not available to a generic model.",
    ),
    CatalogEntry(
        title="AWS SAA-C03 Handbook",
        key="study-docs/aws-saa-handbook.pdf",
        description="Solutions Architect Associate (SAA-C03) study handbook.",
    ),
]


def catalog() -> List[CatalogEntry]:
    """Return the active document catalog (allow-list)."""
    return list(DEFAULT_CATALOG)


def titles() -> List[str]:
    """Human-friendly document titles for the UI selector and the model."""
    return [e.title for e in catalog()]


def key_for_title(title: str) -> str | None:
    """Resolve a catalog title to its S3 key, or None if not permitted."""
    for e in catalog():
        if e.title == title:
            return e.key
    return None


def is_permitted_key(key: str) -> bool:
    """True only if `key` is one of the application-controlled catalog keys."""
    return any(e.key == key for e in catalog())


def available_documents(settings: "Settings | None" = None, s3_client=None) -> List[str]:
    """Return titles of catalog documents that actually exist and are usable.

    A document is "available" only when its S3 object exists, is within the
    size limit, and has a supported file extension. This lets the UI list just
    the working files instead of every catalog entry, so a user can never pick
    a document that will fail on read.

    Uses a cheap HEAD request per object (no download). If the bucket is not
    configured or S3 cannot be reached, returns an empty list rather than
    raising, so the UI can degrade gracefully.
    """
    settings = settings or globals()["settings"]
    if not settings.bucket:
        return []

    # Local import to avoid a module-level boto3 dependency for non-UI callers.
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = s3_client or boto3.client("s3", region_name=settings.aws_region)
    allowed_exts = (".pdf", ".txt", ".md")
    out: List[str] = []
    for e in catalog():
        dot = e.key.rfind(".")
        ext = e.key[dot:].lower() if dot != -1 else ""
        if ext not in allowed_exts:
            continue
        try:
            head = client.head_object(Bucket=settings.bucket, Key=e.key)
        except (ClientError, BotoCoreError):
            # Missing object, access denied, or transient error -> not available.
            continue
        size = int(head.get("ContentLength", 0))
        if 0 < size <= settings.max_bytes:
            out.append(e.title)
    return out
