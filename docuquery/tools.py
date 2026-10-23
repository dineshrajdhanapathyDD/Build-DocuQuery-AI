"""Strands-compatible tool wrapper for the S3 document reader.

The agent sees exactly one new tool: `read_s3_document`. Its docstring is the
contract the model reads, so it enumerates the permitted documents and the
behavior precisely.
"""

from __future__ import annotations

import json

from strands import tool

from . import config
from .s3_reader import read_document


@tool
def read_s3_document(title: str) -> str:
    """Read one of the user's permitted study documents from Amazon S3.

    Use this when a question depends on the content of a specific uploaded
    document (AWS exam notes, whitepapers, service guides, personal study
    notes). You must pass the exact `title` of a permitted document. You cannot
    choose a bucket or an arbitrary file - only the titles listed below are
    allowed.

    Permitted document titles:
    """ + _permitted_titles_block() + """

    Args:
        title: The exact title of a permitted document (see the list above).

    Returns:
        A JSON string. On success:
          {"ok": true, "key": "...", "pages": N, "truncated": bool,
           "text": "extracted text with [page N] markers"}
        On failure:
          {"ok": false, "error_type": "...", "error": "..."}
        where error_type is one of: not_permitted, unsupported_type, oversized,
        missing, access_denied, empty, invalid_pdf, encrypted_pdf, aws_error.
    """
    key = config.key_for_title(title)
    if key is None:
        return json.dumps(
            {
                "ok": False,
                "error_type": "not_permitted",
                "error": (
                    f"'{title}' is not a permitted document. Choose one of: "
                    + ", ".join(config.titles())
                ),
            }
        )

    result = read_document(key)
    payload = result.to_dict()
    # Keep the tool output compact: drop empty fields on failure.
    if not result.ok:
        payload = {
            "ok": False,
            "key": result.key,
            "error_type": result.error_type,
            "error": result.error,
        }
    return json.dumps(payload)


def _permitted_titles_block() -> str:
    lines = [f"      - {t}" for t in config.titles()]
    return "\n" + "\n".join(lines) + "\n"
