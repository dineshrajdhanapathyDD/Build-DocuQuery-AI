# DocuQuery AI: Giving My AWS Exam Agent an Amazon S3 Document Reader

*AWS Builder Center project write-up. Fill in the bracketed links before
publishing. The write-up covers the required hackathon parts (the starting
agent, the one new tool and why, the new behavior) plus how I built it, what I
learned, the architecture, troubleshooting, the tech stack, pricing, and a
conclusion.*

- Code repository: [REPLACE_WITH_REPO_LINK]
- Live app (Streamlit Community Cloud): [REPLACE_WITH_APP_LINK]
- Demo video (under 3 minutes): [REPLACE_WITH_VIDEO_LINK]

---

## The theme: one tool, a clear before/after

The challenge was to take an existing agent and add exactly **one** new tool,
then show the difference it makes. I kept that constraint strict: a single tool,
and a demo that puts the *same agent* answering the *same question* side by side
with the tool off (**Before**) and on (**After**). The whole story is one
sentence: **one tool turned a generic AWS tutor into an agent that answers from
my own private study material, with citations and guardrails.**

## (a) The agent I started with

I started with **DocuQuery AI**, a small AWS certification study assistant built
on the **Strands Agents SDK** with an **Amazon Bedrock** model. Out of the box
it could answer general AWS exam questions from the model's built-in knowledge:
explain services, compare options, and talk through Well-Architected concepts.

What it could **not** do was read any of my own material. My best exam-prep
content lives in private PDFs - personal notes, mnemonics, and a 299-page
SAA-C03 handbook - sitting in an Amazon S3 bucket. The base agent had no way to
open them, so for any question that depended on *my* notes it could only guess
or give a generic answer.

## (b) The one new tool I added, and why

I added exactly one tool: **`read_s3_document`**, an Amazon S3 document reader.

I picked S3 because it is where my study material already lives, and because a
"read my private document" capability is the single highest-leverage thing a
study agent can gain - it turns a generic tutor into one that knows *my*
curriculum. The tool:

- accepts a document **title** chosen from an application-controlled allow-list
  (the model can never name an arbitrary bucket or key);
- fetches the object with **boto3** using a configured bucket and region;
- validates file **type and size** before processing;
- extracts text from PDFs with **pypdf** (plain text and Markdown are also
  supported);
- returns the extracted text with `[page N]` markers plus metadata, capped to a
  sensible length; and
- handles missing objects, invalid or encrypted PDFs, empty documents,
  oversized files, and AWS permission errors as clear, typed results.

Security was a first-class design goal: the bucket is fixed in configuration,
keys are allow-listed, there are no hardcoded credentials (boto3's standard
provider chain is used), and the IAM policy grants read access only to the
`study-docs/*` prefix plus Bedrock invoke on a single model.

## (c) The new behavior the tool unlocked

**Before:** ask *"According to my SAA-C03 handbook, what are the exact
throughput limits of a single Kinesis Data Streams shard?"* and the agent gives
a vague, uncited answer - it has no way to open my document.

**After:** the same agent, same question - it recognizes the question depends on
a document, calls `read_s3_document`, pulls the handbook from S3, and answers
*"1 MB/s write, 2 MB/s read per shard"* **with a page citation (`[page 22]`)**.
It labels what came **from the document** separately from **general AWS
knowledge**, and when a document doesn't contain the answer it says so instead
of inventing one.

I verified this live against a real AWS account (see "Troubleshooting" and the
repo's `docs/live_demo_results.md`), and in a self-correcting moment the model
first tried an *unpermitted* title, the allow-list rejected it, and the agent
retried with a permitted title - proving the model cannot reach arbitrary keys.

## How I built it

I built it in Option-B style - a clean baseline agent first, then the one tool -
so the before/after contrast is honest and the tool is the only variable.

1. **Config as the security boundary (`docuquery/config.py`).** A `Settings`
   dataclass resolves region, bucket, model, and limits from environment
   variables, and a `DEFAULT_CATALOG` defines the allow-list of
   `title -> S3 key` mappings. The model only ever sees titles.
2. **The reader (`docuquery/s3_reader.py`).** A pure, dependency-injectable
   `read_document(key, *, settings, s3_client)` that enforces the allow-list,
   HEAD-checks size before downloading, extracts text with pypdf, and returns a
   typed `DocumentResult` (`ok`, `pages`, `char_count`, `truncated`,
   `error_type`, ...). Keeping it pure made it trivial to unit-test with a fake
   S3 client.
3. **The tool (`docuquery/tools.py`).** A thin `@tool`-decorated
   `read_s3_document(title)` wrapper that the Strands agent can call; it returns
   a JSON string the model can reason over.
4. **Two agents (`docuquery/agent.py`).** `build_base_agent()` (no tools) and
   `build_enhanced_agent()` (with the one tool) share the same model so the only
   difference is the tool.
5. **UI (`app.py`).** A Streamlit app with a Before/After toggle, a document
   selector that lists **only readable documents**, a question box, an answer
   panel, and a source panel showing document name, key, and page count.
6. **Tests (`tests/`).** Twelve mocked unit tests cover success, unsupported
   type, missing object, invalid PDF, encrypted PDF, empty PDF, oversized, and
   permission denial - all offline, no AWS calls.
7. **Deploy.** Pushed to GitHub and made Streamlit-Community-Cloud-ready: config
   reads `st.secrets` and bridges them into `os.environ`, so the exact same code
   runs locally (`.env`) and on Cloud (dashboard Secrets).

## Technology stack

| Layer | Technology | Role |
| --- | --- | --- |
| Agent framework | **Strands Agents SDK** (`strands-agents` 1.62) | Agent loop and the `@tool` decorator for `read_s3_document` |
| Reasoning model | **Amazon Bedrock - Amazon Nova Pro** (`amazon.nova-pro-v1:0`) | Natural-language reasoning and tool-calling |
| Storage | **Amazon S3** | Private study documents under a `study-docs/` prefix |
| AWS SDK | **boto3 / botocore** | S3 `head_object` / `get_object`, standard credential chain |
| PDF parsing | **pypdf** 5.9 | Text extraction with per-page markers |
| UI | **Streamlit** 1.66 | Before/After UI, document selector, source panel |
| Identity & access | **AWS IAM** (least-privilege user + inline policy) | Scoped read to `study-docs/*` + Bedrock invoke on one model |
| Language / runtime | **Python 3.12** | Project runtime |
| Testing | **pytest** | 12 mocked unit tests, no live AWS required |
| Hosting | **Streamlit Community Cloud** | Public demo deployment |
| Source control | **GitHub** | Repo; secrets git-ignored, never committed |

## Architecture

The request flow (also in `docs/architecture.md` as a Mermaid diagram and in
`docs/architecture.drawio` as an editable draw.io file):

1. The user picks a document (from the allow-list) and asks a question in the
   Streamlit UI.
2. The Strands agent (Amazon Bedrock / Nova Pro) decides whether the question
   needs a document.
3. **After** mode: it calls `read_s3_document` with the document **title**.
4. `config.key_for_title` maps the title to an approved S3 key; any title or key
   not in the catalog is rejected before any AWS call.
5. `read_document` validates type and size, fetches the object from the
   configured bucket/region with boto3, extracts text with pypdf, and returns
   text (with `[page N]` markers) plus metadata, truncated to a length limit.
6. The agent composes an answer that labels document evidence separately from
   general AWS knowledge; the UI shows a source panel with the document name and
   page references.
7. **Before** mode: the agent has no tool, so it never reaches S3 - the contrast
   the demo depends on.

**Security boundaries:** fixed bucket in config, allow-listed keys (title-only
selection), no hardcoded credentials (boto3 provider chain), and least-privilege
IAM (`study-docs/*` read + Bedrock invoke on one model).

## Troubleshooting (things that actually bit me)

- **Model access: Claude denied, Nova Pro worked.** My first model choice
  returned `AccessDenied` from Bedrock in this account. I probed model
  availability and switched to `amazon.nova-pro-v1:0`, which is enabled and
  invokable - a reminder that Bedrock model access is per-account/per-region and
  must be verified, not assumed.
- **Dependency version conflict.** My initial pins (`boto3==1.35.76` plus an
  extra tools package) produced a botocore conflict. I relaxed the pins to a
  working set (strands-agents 1.62, boto3 1.43, pypdf 5.9, streamlit 1.66).
- **`UnrecognizedClientException` on `ConverseStream` in the deployed app.** The
  live Streamlit Cloud app failed with an invalid-security-token error while the
  exact same code worked locally. Root cause: **Streamlit Cloud never reads the
  repo's `.env`** - it only uses the Secrets pasted into its dashboard, which
  were stale. Fix: paste the current credentials into the Cloud Secrets panel and
  reboot. I confirmed the credentials themselves were valid by testing `converse`
  and `converse_stream` directly from a clean process.
- **Copyright hygiene.** My first sample PDF was a copyrighted slide deck marked
  "not for distribution." I removed it from both S3 and local disk and replaced
  it with a non-copyrighted SAA-C03 handbook, keeping the public repo clean. All
  study PDFs are git-ignored and live only in S3.
- **"Show only working documents."** The selector originally listed every
  catalog entry, so a missing or unreadable object would still appear and fail on
  ask. I added `config.available_documents()`, which HEAD-checks each catalog
  object and returns only titles that truly exist and are within the size limit;
  the UI caches this and warns clearly when nothing is readable (which, usefully,
  also signals a credentials problem on Cloud).

## Pricing

The project is intentionally cheap to run; the only metered pieces are Bedrock
inference and a tiny amount of S3.

- **Amazon Bedrock - Nova Pro:** billed per 1K input/output tokens
  (on-demand). A single study question is a few thousand tokens total, so each
  interaction costs a fraction of a cent. There is no idle cost - you pay only
  per request.
- **Amazon S3:** a handful of small PDFs (the handbook is ~4 MB). Storage is
  well under 1 GB, so storage cost is negligible; requests are `HEAD`/`GET` per
  question, billed per thousand requests - effectively rounding to zero at demo
  scale.
- **AWS IAM:** free.
- **Streamlit Community Cloud:** free tier hosts the public demo.
- **Data transfer:** S3 `GET` within the same region to the app is minimal;
  truncating extracted text to a character cap also bounds token cost.

Net effect: at demo and personal-study scale this runs for pennies, and it has
no standing/idle charges because both Bedrock and S3 are pay-per-use.

## What I learned

- **One well-chosen tool beats many.** Constraining myself to a single tool made
  the value obvious and the demo honest. The hard design work wasn't the tool's
  happy path - it was the allow-list, the typed error results, and the
  before/after framing.
- **Make the tool a security boundary, not just a feature.** Letting the model
  pick only a *title* (never a bucket or key) is what makes "read my documents"
  safe. The allow-list rejecting an unpermitted title - and the agent
  self-correcting - was the moment the design proved itself.
- **Grounding needs honesty guardrails.** Returning typed results (including
  "empty" / "not permitted") and labeling document evidence vs general knowledge
  is what stops a RAG-style agent from confidently making things up.
- **Local success != deployed success.** The `UnrecognizedClientException` taught
  me that Streamlit Cloud's secret model is separate from local `.env`; "works on
  my machine" hides an entire credential-delivery path.
- **Verify, don't assume, on AWS.** Bedrock model access and dependency
  compatibility both needed real checks, not guesses.
- **Keep mocked and live testing separate.** Twelve offline mocked tests give
  fast, deterministic confidence; a documented live run proves the real
  S3+Bedrock path. Conflating the two would have hidden problems.

## Conclusion

DocuQuery AI shows that a single, carefully designed tool can transform an
agent's usefulness. `read_s3_document` took a capable-but-generic AWS tutor and
made it answer from *my* private study material - with page citations, an
application-controlled allow-list, least-privilege IAM, and honest "I don't have
that in the document" behavior. The before/after demo makes the difference
unmistakable, the mocked tests keep it verifiable offline, and a documented live
run proves it works against real Amazon S3 and Amazon Bedrock.

If I extended it, the natural next steps are true chunked retrieval/embeddings
for very large corpora (Amazon Bedrock Knowledge Bases), multi-document
synthesis, and per-user allow-lists - but the core lesson stands: **pick the one
tool that changes what the agent can honestly claim to know, and build it as a
boundary, not just a feature.**

## Honest scope note

The mocked unit tests run offline and pass (12 passed). The live Amazon S3 +
Amazon Bedrock path is exercised via `demo_before_after.py` and the Streamlit
app, and requires real AWS credentials, Bedrock model access, and a bucket
containing the documents. Mocked and live testing are kept clearly separate.
