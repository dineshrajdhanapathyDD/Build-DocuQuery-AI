# DocuQuery AI - Architecture

## Mermaid diagram

```mermaid
flowchart TD
    User([User]) -->|question + chosen document| UI[Streamlit app<br/>app.py]

    UI -->|invokes| Agent[Strands Agent<br/>Amazon Bedrock model]

    subgraph Enhanced["Enhanced agent (AFTER)"]
        Agent -->|decides a document is needed| Tool["read_s3_document tool<br/>docuquery/tools.py"]
        Tool -->|title to key| Allowlist[["Application allow-list<br/>docuquery/config.py"]]
        Allowlist -->|permitted key only| Reader[read_document<br/>docuquery/s3_reader.py]
    end

    Reader -->|head_object / get_object<br/>configured bucket + region| S3[(Amazon S3<br/>study-docs/ prefix)]
    Reader -->|pypdf text extraction<br/>type/size/empty checks| Reader
    Reader -->|text + page markers + metadata| Tool
    Tool -->|JSON result| Agent
    Agent -->|answer: document evidence vs<br/>general AWS knowledge| UI
    UI -->|answer + source panel<br/>doc name + pages| User

    Agent -. uses general knowledge only .-> BaseNote["BEFORE agent has no tool,<br/>so it cannot reach S3"]

    classDef aws fill:#ff9900,stroke:#232f3e,color:#232f3e;
    classDef guard fill:#e8f0fe,stroke:#1a73e8,color:#1a3d8f;
    class S3,Agent aws;
    class Allowlist guard;
```

## How the request flows

1. The user picks a document (from the allow-list) and types a question in the
   Streamlit UI.
2. The Strands agent (backed by an Amazon Bedrock model) decides whether the
   question needs a document.
3. If so, it calls the single new tool, `read_s3_document`, with the document
   **title** (never a raw key or bucket).
4. `config.key_for_title` maps the title to an approved S3 key. Any title or
   key not in the catalog is rejected before any AWS call.
5. `read_document` validates type and size, fetches the object from the
   configured bucket/region with boto3, extracts text with pypdf, and returns
   text (with `[page N]` markers) plus metadata, truncated to a length limit.
6. The agent composes an answer that labels document evidence separately from
   general AWS knowledge, and the UI shows a source panel with the document
   name and page references.

## Security boundaries

- **Bucket is fixed** in configuration; the model cannot change it.
- **Keys are allow-listed**; the model selects by title only.
- **No hardcoded credentials** - boto3's standard provider chain (IAM role,
  profile, env vars, SSO) supplies credentials.
- **Least privilege IAM** - read only the `study-docs/*` prefix plus Bedrock
  invoke (see `docs/iam-policy.json`).
