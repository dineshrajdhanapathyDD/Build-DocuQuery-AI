"""Generate a small sample study PDF and (optionally) upload it to S3.

This gives you a real private document for the before/after demo without
needing to author one by hand. The PDF contains a made-up "memory trick" so
you can prove the enhanced agent is reading YOUR document, not reciting public
AWS docs.

Usage:
  # Just write a local PDF:
  python scripts/make_sample_pdf.py

  # Write locally AND upload to the configured bucket/key:
  python scripts/make_sample_pdf.py --upload
"""

from __future__ import annotations

import argparse
import io
import os
import sys

# Allow running from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docuquery import config  # noqa: E402


SAMPLE_TEXT_PAGES = [
    (
        "AWS Solutions Architect - Personal Study Notes\n\n"
        "S3 Storage Class memory trick (mine): 'Students Idly Omit Gym On "
        "Fridays, Generally.'\n"
        "  S = Standard (hot data)\n"
        "  I = Intelligent-Tiering (unknown/changing access)\n"
        "  O = One Zone-IA (reproducible, infrequent)\n"
        "  G = Glacier Instant Retrieval (archive, ms access)\n"
        "  O = (Glacier Flexible) - minutes to hours\n"
        "  F = Glacier Deep Archive (coldest, cheapest)\n"
    ),
    (
        "Durability vs Availability (my shorthand):\n"
        "  Durability = 'will I lose it?' (11 nines across classes).\n"
        "  Availability = 'can I reach it right now?' (varies by class).\n"
        "Exam trap I keep failing: One Zone-IA has LOWER availability because "
        "it lives in a single AZ.\n"
    ),
]


def build_pdf(pages: list[str]) -> bytes:
    """Build a valid multi-page PDF with extractable text (no reportlab)."""
    header = b"%PDF-1.4\n"
    objects: list[bytes] = []
    page_obj_nums: list[int] = []
    next_num = 3
    page_chunks: list[bytes] = []

    for text in pages:
        page_num = next_num
        content_num = next_num + 1
        next_num += 2
        page_obj_nums.append(page_num)

        # One Tj per line, moving the text cursor down with TL/T*.
        lines = text.split("\n")
        body = b"BT /F1 11 Tf 40 760 Td 14 TL "
        for ln in lines:
            safe = (
                ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            ).encode("latin-1", "replace")
            body += b"(" + safe + b") Tj T* "
        body += b"ET"

        page_chunks.append(
            (
                f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 612 792] /Contents {content_num} 0 R "
                f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 "
                f"/BaseFont /Helvetica >> >> >> >>\nendobj\n"
            ).encode()
        )
        page_chunks.append(
            f"{content_num} 0 obj\n<< /Length {len(body)} >>\nstream\n".encode()
            + body
            + b"\nendstream\nendobj\n"
        )

    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>\nendobj\n".encode()
    )
    objects.extend(page_chunks)

    total = 2 + 2 * len(pages)
    out = bytearray(header)
    offsets = [0] * (total + 1)
    for i, obj in enumerate(objects, start=1):
        offsets[i] = len(out)
        out.extend(obj)

    xref_start = len(out)
    out.extend(f"xref\n0 {total + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for i in range(1, total + 1):
        out.extend(f"{offsets[i]:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {total + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode()
    )
    return bytes(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true", help="upload to S3")
    parser.add_argument(
        "--out", default="sample_docs/saa-personal-notes.pdf", help="local output path"
    )
    args = parser.parse_args()

    pdf = build_pdf(SAMPLE_TEXT_PAGES)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wb") as fh:
        fh.write(pdf)
    print(f"Wrote {args.out} ({len(pdf)} bytes)")

    if args.upload:
        import boto3

        bucket = config.settings.bucket
        if not bucket:
            print("DOCUQUERY_BUCKET not set; cannot upload.")
            return 2
        key = config.catalog()[0].key  # first catalog entry = personal notes
        boto3.client("s3", region_name=config.settings.aws_region).put_object(
            Bucket=bucket, Key=key, Body=pdf, ContentType="application/pdf"
        )
        print(f"Uploaded to s3://{bucket}/{key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
