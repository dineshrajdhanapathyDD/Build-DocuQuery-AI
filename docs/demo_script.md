# Two-minute demo script (video walkthrough)

Target length: under 2 minutes. Keep it tight - show the before/after contrast
clearly. Timings are a guide.

---

**[0:00-0:15] Hook + setup**

> "This is DocuQuery AI, an AWS exam-prep agent built with the Strands Agents
> SDK on Amazon Bedrock. I gave it exactly one new tool: an Amazon S3 document
> reader. Watch what changes."

Show the Streamlit app running (`streamlit run app.py`). Point at the document
selector, the question box, and the Before/After toggle in the sidebar.

---

**[0:15-0:50] BEFORE - original agent, no tool**

- Switch the sidebar toggle to **Before (no S3 tool)**.
- Ask: *"According to my personal study notes, what is my memory trick for
  choosing between S3 storage classes? Cite the page."*
- Narrate:

> "The original agent only has general AWS knowledge. It has no way to open my
> private PDF, so it can't give my personal mnemonic - and it says so instead
> of making one up."

Show the answer admitting it can't see the document. The source panel shows
"no document sources."

---

**[0:50-1:40] AFTER - enhanced agent, with read_s3_document**

- Switch the toggle to **After (with S3 tool)**.
- Keep the **same document selected** and ask the **same question**.
- Narrate:

> "Same agent, same question - but now it has the read_s3_document tool. It
> picks my permitted document by title, the tool enforces an allow-list,
> downloads it from S3, extracts the text with pypdf, and answers from MY
> notes - with a page citation."

Show:
- The answer containing the personal mnemonic ("Students Idly Omit Gym On
  Fridays, Generally").
- The answer labeling "From the document" vs "General AWS knowledge".
- The **Source panel**: document name, key, page count, and a text preview.

---

**[1:40-2:00] Safety + wrap**

> "The model never chooses a bucket or an arbitrary key - it can only pick from
> an application-controlled list, with least-privilege IAM. One tool turned a
> generic assistant into one that answers from my own private study material."

Optionally flash the terminal running `python demo_before_after.py` to show the
same contrast outside the UI, and `pytest` showing the mocked tests pass.

---

## Sample questions (matched to the uploaded PDF)

The uploaded document `study-docs/saa-personal-notes.pdf` contains a personal
mnemonic (page 1) and a personal "exam trap" note (page 2). The best demo
questions are framed with **"my notes / my trick / my shorthand"** so the
answer can only come from that PDF - that is what makes the before/after gap
visible.

### Hero question (use this for the main before/after)

> According to my personal study notes, what is my memory trick for choosing
> between S3 storage classes? Cite the page.

- **Before:** admits it cannot access your private notes; gives generic storage
  info only.
- **After:** recites your exact mnemonic *"Students Idly Omit Gym On Fridays,
  Generally"* with `[page 1]`, labeling document evidence vs general knowledge.

### Backup: page-2 question (proves it reads the whole document)

> In my notes, what is the "exam trap I keep failing" about S3 One Zone-IA?

- **After:** One Zone-IA has **lower availability** because it lives in a single
  AZ, cited from `[page 2]`.

> What's my personal shorthand for durability vs availability?

- **After:** *"Durability = will I lose it? Availability = can I reach it right
  now?"* - clearly your phrasing, from `[page 2]`.

### Baseline: general AWS question (both modes answer well)

> What's the difference between S3 Standard-IA and S3 One Zone-IA?

- **Both modes** answer this correctly from general knowledge. Use it to show
  the agent is still a capable AWS tutor - the tool adds to it, nothing is lost.

### Guardrail / honesty question (optional, powerful)

> According to my notes, what does my professor say about DynamoDB capacity
> modes?

- **After:** the document has nothing about DynamoDB, so the agent says there is
  not enough evidence in the document instead of inventing an answer.

### Recommended 2-question flow for the video

1. Ask the **baseline** general question in both modes -> "it already knows AWS."
2. Ask the **hero** private-notes question in both modes -> "now it also knows
   MY notes." That contrast is the whole story.

> Tip: avoid questions whose answers are common AWS knowledge without a personal
> framing (e.g. "What are the S3 storage classes?"). Both modes answer those, so
> there is no visible before/after difference.

---

## Sample questions (matched to the SAA-C03 Handbook)

The document `study-docs/aws-saa-handbook.pdf` ("AWS Solutions Architect
Associate (SAA-C03) Handbook", 299 pages) contains exact service limits and
"Exam Tips" lines. The strongest demo questions target a **specific number or
exam-tip phrase** from the handbook: the After agent can cite it with a page
reference, while the Before agent can only give a general or hedged answer.

Frame each question with **"according to my SAA-C03 handbook / from my notes"**
so the answer is expected to come from that document.

### Hero question (crisp numbers, best single before/after)

> According to my SAA-C03 handbook, what are the exact read and write throughput
> limits of a single Kinesis Data Streams shard? Cite the page.

- **Before:** vague or ballpark answer, no source, may state limits incorrectly.
- **After:** *"Each shard: 1 MB/s write, 2 MB/s read"* with `[page 22]`, read
  from the handbook via `read_s3_document`.

### Backup questions (exact facts from the handbook)

> From my handbook, what is the transactions-per-second limit for an SQS FIFO
> queue, and how can it be increased?

- **After:** *"Up to 300 TPS, can increase with batching"* `[page 54]`.

> In my SAA-C03 handbook, how many ways is Aurora storage replicated, across how
> many Availability Zones, and how long does failover take?

- **After:** *"Six-way replication across three AZs; failover typically under 30
  seconds"* `[pages 96/99]`.

### Exam-tip recall (the "wow" question)

> My handbook has an exam tip on the difference between a DynamoDB LSI and a GSI.
> What does it say?

- **After:** *"LSI must be defined at creation; GSI can be added anytime"*
  `[page 104]` - quotes the handbook's own Exam Tips line almost verbatim.

### Guardrail / honesty question (proves grounding)

> What does my SAA-C03 handbook say about Amazon Bedrock pricing tiers?

- **After:** Bedrock is not covered in this handbook, so the agent reads the
  document and honestly reports there is no such content - instead of answering
  from general knowledge. This shows the answer is grounded in the document.

### Recommended 2-question flow for the video (handbook)

1. Ask the **hero** Kinesis-shard question in both modes -> Before is vague,
   After cites "1 MB/s write, 2 MB/s read `[page 22]`."
2. Ask the **exam-tip** LSI-vs-GSI question in After mode -> it quotes the
   handbook's own Exam Tips line with a page number. That is the whole story.

---

## Pre-recording checklist

- [ ] `.env` created from `.env.example` with a real `DOCUQUERY_BUCKET`.
- [ ] Both catalog documents exist in S3 under `study-docs/`:
      `saa-personal-notes.pdf` and `aws-saa-handbook.pdf`.
- [ ] The document selector lists both docs (it only shows readable files).
- [ ] Bedrock model access enabled for `BEDROCK_MODEL_ID` (amazon.nova-pro-v1:0)
      in your region.
- [ ] AWS credentials available via role/profile (no keys on screen).
- [ ] `streamlit run app.py` works and both modes respond.
- [ ] (If demoing the deployed app) Streamlit Cloud Secrets match the current
      local `.streamlit/secrets.toml`, then reboot the app.
