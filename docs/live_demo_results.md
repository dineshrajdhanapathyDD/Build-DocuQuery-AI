# Live demo results (real AWS run)

Captured from a real run against this machine's AWS account on 2026-10-23.

- **Account:** 466742534146 (IAM user `DD-IAM-ADMIN`)
- **Region:** us-east-1
- **Bucket:** `docuquery-ai-study-466742534146-us-east-1`
- **Document:** `study-docs/saa-personal-notes.pdf` (2 pages, uploaded by `scripts/make_sample_pdf.py --upload`)
- **Model:** `amazon.nova-pro-v1:0` (Amazon Bedrock, verified invokable in this account)

Both the terminal demo (`demo_before_after.py`) and the Streamlit UI (driven in
a real browser) produced the same contrast. The UI configuration readout showed
the live bucket and model.

## Question (identical in both modes)

> According to my personal study notes, what is my memory trick for choosing
> between S3 storage classes? Cite the page.

## BEFORE - original agent (no `read_s3_document` tool)

Verbatim (abridged) response:

> I'm sorry, but I can't access or reference personal study notes or private
> documents. Each individual may have their own unique memory tricks or
> mnemonics for remembering AWS S3 storage classes.
>
> However, here's a general guide ... [generic S3 Standard / Intelligent-Tiering
> / Standard-IA / One Zone-IA / Glacier / Glacier Deep Archive descriptions] ...
>
> If you have a specific memory trick in your notes, you'll need to refer to
> them directly.

Source panel: *"Before mode: the original agent has no document access, so there
are no document sources."*

**Result: the original agent cannot read the private PDF.** It correctly refuses
to invent the user's personal mnemonic.

## AFTER - enhanced agent (with `read_s3_document`)

The agent called the tool, the allow-list resolved the permitted title to the
S3 key, and the document was fetched and extracted live. Verbatim response:

> From the document:
> - Memory trick for choosing between S3 storage classes: "Students Idly Omit
>   Gym On Fridays, Generally." [page 1]
>   - S = Standard (hot data)
>   - I = Intelligent-Tiering (unknown/changing access)
>   - O = One Zone-IA (reproducible, infrequent)
>   - G = Glacier Instant Retrieval (archive, ms access)
>   - O = (Glacier Flexible) - minutes to hours
>   - F = Glacier Deep Archive (coldest, cheapest) [page 1]

Source panel: **Document:** AWS Solutions Architect Study Notes (personal) /
**Key:** `study-docs/saa-personal-notes.pdf` / **Pages:** 2 / preview expander.

**Result: the enhanced agent retrieved the private note from S3 and answered
with the user's exact mnemonic and a page citation,** labeling document evidence
separately from general AWS knowledge.

## Guardrail observed live

In the terminal run, the model first tried an unpermitted title
(`personal_study_notes`). The allow-list rejected it (`not_permitted`), and the
agent self-corrected to the permitted title before succeeding. This demonstrates
that the model cannot reach arbitrary keys - only catalog titles resolve.

## Tests

`python -m pytest` -> **12 passed** (mocked; no AWS calls). See README.
