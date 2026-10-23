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

## Pre-recording checklist

- [ ] `.env` created from `.env.example` with a real `DOCUQUERY_BUCKET`.
- [ ] Sample PDF uploaded: `python scripts/make_sample_pdf.py --upload`.
- [ ] Bedrock model access enabled for `BEDROCK_MODEL_ID` in your region.
- [ ] AWS credentials available via role/profile (no keys on screen).
- [ ] `streamlit run app.py` works and both modes respond.
