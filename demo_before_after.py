"""Before-and-after demonstration for DocuQuery AI.

Runs the SAME question against:
  BEFORE - the original agent (no S3 tool), which cannot see private study PDFs.
  AFTER  - the enhanced agent (with `read_s3_document`), which retrieves and
           answers from the private document.

This script makes LIVE AWS calls (Amazon Bedrock + Amazon S3). It will only
work with real credentials, model access, and a bucket containing the catalog
documents. Without those it prints a clear message and exits - it never fakes
a result.

Usage:
    python demo_before_after.py
    python demo_before_after.py --question "Your question here"
"""

from __future__ import annotations

import argparse
import sys

from docuquery import config
from docuquery.agent import build_base_agent, build_enhanced_agent


DEFAULT_QUESTION = (
    "According to my personal study notes, what is my memory trick for choosing "
    "between S3 storage classes? Cite the page."
)


def _print_header(label: str) -> None:
    print("\n" + "=" * 72)
    print(label)
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="DocuQuery AI before/after demo")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    if not config.settings.bucket:
        print(
            "DOCUQUERY_BUCKET is not set. Copy .env.example to .env and set a "
            "real bucket before running the live demo."
        )
        return 2

    print(f"Region : {config.settings.aws_region}")
    print(f"Bucket : {config.settings.bucket}")
    print(f"Model  : {config.settings.model_id}")
    print(f"Question:\n  {args.question}")

    _print_header("BEFORE - original agent (no document access)")
    try:
        base = build_base_agent()
        before = base(args.question)
        print(before)
    except Exception as exc:  # noqa: BLE001 - surface any live-AWS failure
        print(f"[live AWS call failed] {type(exc).__name__}: {exc}")
        return 1

    _print_header("AFTER - enhanced agent (with read_s3_document)")
    try:
        enhanced = build_enhanced_agent()
        after = enhanced(args.question)
        print(after)
    except Exception as exc:  # noqa: BLE001
        print(f"[live AWS call failed] {type(exc).__name__}: {exc}")
        return 1

    _print_header("DONE")
    print(
        "The BEFORE agent answers only from general knowledge and cannot read "
        "your private PDF. The AFTER agent uses read_s3_document to retrieve "
        "the document and answer with page citations."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
