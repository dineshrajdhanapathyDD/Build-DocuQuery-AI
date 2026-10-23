"""Agent factory for DocuQuery AI.

Two builders produce the *before* and *after* agents used in the demo:

  * `build_base_agent()`     - the original AWS-knowledge agent. No document
                               access; answers purely from general knowledge.
  * `build_enhanced_agent()` - the same agent plus the single new tool
                               `read_s3_document`, which lets it read the user's
                               private S3 study documents.

Keeping both in one place makes the before/after contrast explicit and keeps
the base agent's behavior preserved exactly when the tool is added.
"""

from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from . import config
from .tools import read_s3_document


BASE_SYSTEM_PROMPT = (
    "You are DocuQuery AI, an expert assistant for AWS certification exam "
    "preparation (Solutions Architect, Developer, SysOps, and the foundational "
    "exams). Answer clearly and concisely using well-established AWS knowledge. "
    "If you are unsure or a question depends on a private document you cannot "
    "see, say so plainly rather than guessing."
)

ENHANCED_SYSTEM_PROMPT = (
    BASE_SYSTEM_PROMPT
    + "\n\nYou now have a tool, `read_s3_document`, that reads the user's "
    "permitted study documents from Amazon S3. Use it whenever a question "
    "depends on the content of a specific uploaded document. When you answer "
    "from a document, clearly label that part as 'From the document' and cite "
    "page numbers using the [page N] markers in the extracted text. Separately "
    "label any 'General AWS knowledge' you add. If the document does not "
    "contain enough evidence to answer, say so explicitly and do not invent "
    "details."
)


def _model() -> BedrockModel:
    return BedrockModel(
        model_id=config.settings.model_id,
        region_name=config.settings.aws_region,
        temperature=0.2,
    )


def build_base_agent() -> Agent:
    """The original agent: general AWS knowledge, no document access."""
    return Agent(
        model=_model(),
        system_prompt=BASE_SYSTEM_PROMPT,
    )


def build_enhanced_agent() -> Agent:
    """The enhanced agent: original capabilities plus the S3 reader tool."""
    return Agent(
        model=_model(),
        tools=[read_s3_document],
        system_prompt=ENHANCED_SYSTEM_PROMPT,
    )
