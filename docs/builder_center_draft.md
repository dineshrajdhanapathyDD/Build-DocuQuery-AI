# DocuQuery AI: Giving My AWS Exam Agent an Amazon S3 Document Reader

*(Draft for the AWS Builder Center project write-up. Fill in the bracketed
links before publishing. This write-up intentionally covers the three required
parts: the starting agent, the one new tool and why, and the new behavior.)*

## (a) The agent I started with

I started with **DocuQuery AI**, a small AWS certification study assistant built
on the **Strands Agents SDK** with an **Amazon Bedrock** model. Out of the box
it could answer general AWS exam questions from the model's built-in knowledge:
explain services, compare options, and talk through Well-Architected concepts.

What it could **not** do was read any of my own material. My best exam-prep
content lives in private PDFs - personal notes, mnemonics, and summarized
whitepapers - sitting in an Amazon S3 bucket. The base agent had no way to open
them, so for any question that depended on *my* notes it could only guess or
give a generic answer.

## (b) The one new tool I added, and why

I added exactly one tool: **`read_s3_document`**, an Amazon S3 document reader.

I picked S3 because it is where my study material already lives, and because a
"read my private document" capability is the single highest-leverage thing a
study agent can gain. It turns a generic tutor into one that knows *my*
curriculum. The tool:

- accepts a document **title** chosen from an application-controlled allow-list
  (the model can never name an arbitrary bucket or key);
- fetches the object with **boto3** using a configured bucket and region;
- validates file **type and size** before processing;
- extracts text from PDFs with **pypdf** (plain text and Markdown are also
  supported and documented);
- returns the extracted text with `[page N]` markers plus metadata, capped to a
  sensible length; and
- handles missing objects, invalid or encrypted PDFs, empty documents,
  oversized files, and AWS permission errors as clear, typed results.

Security was a first-class design goal: the bucket is fixed in configuration,
keys are allow-listed, there are no hardcoded credentials (boto3's standard
provider chain is used), and the example IAM policy grants read access only to
the `study-docs/*` prefix plus Bedrock invoke.

## (c) The new behavior the tool unlocked

Before: ask "what's my memory trick for S3 storage classes?" and the agent
admits it can't see my notes.

After: the same agent, same question - it recognizes the question depends on a
document, calls `read_s3_document`, pulls my personal notes from S3, and answers
with my own mnemonic **and a page citation**. Crucially, it labels what came
**from the document** separately from **general AWS knowledge**, and when a
document doesn't contain enough evidence it says so instead of inventing an
answer.

That is the whole story in one sentence: **one tool turned a generic AWS tutor
into an agent that answers from my private study material, with citations and
guardrails.**

## How it's built

- **Strands Agents SDK** - the agent and the `@tool`-decorated `read_s3_document`.
- **Amazon Bedrock** - the reasoning model.
- **Amazon S3 + boto3** - private document storage and retrieval.
- **pypdf** - PDF text extraction.
- **Streamlit** - a simple UI with a document selector, question box, answer
  panel, and a source panel showing document name and page references.

Architecture diagram, IAM policy, and mocked unit tests (successful retrieval,
invalid type, missing object, PDF failure, empty PDF, permission denial) are in
the repository.

## Links

- Code repository: [REPLACE_WITH_REPO_LINK]
- Demo video (under 3 minutes): [REPLACE_WITH_VIDEO_LINK]

## Honest scope note

The mocked unit tests run offline and pass. The live Amazon S3 + Amazon Bedrock
path is exercised via `demo_before_after.py` and the Streamlit app, and requires
real AWS credentials, Bedrock model access, and a bucket containing the sample
document. Mocked and live testing are kept clearly separate.
