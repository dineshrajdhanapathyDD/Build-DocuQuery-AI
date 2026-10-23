"""Streamlit UI for DocuQuery AI.

Layout:
  * Sidebar: mode toggle (Before / After), config readout.
  * Document selector (the application-controlled allow-list).
  * Question input + Ask button.
  * Answer panel.
  * Source panel: document name and page references when available.

The app talks to the live agents (Amazon Bedrock + Amazon S3). Run it with:
    streamlit run app.py
"""

from __future__ import annotations

import json

import streamlit as st

from docuquery import config
from docuquery.agent import build_base_agent, build_enhanced_agent
from docuquery.s3_reader import read_document


st.set_page_config(page_title="DocuQuery AI", page_icon="📄", layout="wide")

st.title("📄 DocuQuery AI - AWS Exam Knowledge Agent")
st.caption(
    "Ask questions about your AWS study material. The enhanced agent can read "
    "your private documents from Amazon S3 using the `read_s3_document` tool."
)

# ---------------------------------------------------------------------------
# Sidebar: mode + configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Mode")
    mode = st.radio(
        "Agent mode",
        options=["After (with S3 tool)", "Before (no S3 tool)"],
        help=(
            "Before = original agent, general AWS knowledge only.\n"
            "After = enhanced agent that can read your S3 documents."
        ),
    )

    st.header("Configuration")
    st.write(f"**Region:** `{config.settings.aws_region}`")
    st.write(f"**Bucket:** `{config.settings.bucket or '(not set)'}`")
    st.write(f"**Model:** `{config.settings.model_id}`")
    if not config.settings.bucket:
        st.warning(
            "DOCUQUERY_BUCKET is not set. Copy .env.example to .env and set a "
            "real bucket to enable live document reading."
        )

# ---------------------------------------------------------------------------
# Main: document selector + question
# ---------------------------------------------------------------------------
col_q, col_src = st.columns([3, 2])

with col_q:
    st.subheader("1. Choose a document")
    selected_title = st.selectbox("Available documents", options=config.titles())

    st.subheader("2. Ask a question")
    question = st.text_area(
        "Your question",
        placeholder="e.g. What does my study note say about S3 storage classes?",
        height=100,
    )
    ask = st.button("Ask", type="primary")

with col_src:
    st.subheader("Source")
    src_placeholder = st.empty()
    src_placeholder.info("Source details will appear here after you ask.")


def _augment_question(q: str, title: str) -> str:
    """Nudge the agent toward the chosen document without hiding the question."""
    return (
        f"{q}\n\n(If this depends on a document, read the permitted document "
        f"titled: '{title}'.)"
    )


if ask:
    if not question.strip():
        st.error("Please enter a question.")
    elif not config.settings.bucket:
        st.error("No bucket configured. Set DOCUQUERY_BUCKET in your .env file.")
    else:
        st.subheader("Answer")
        with st.spinner("Thinking..."):
            try:
                if mode.startswith("After"):
                    agent = build_enhanced_agent()
                    prompt = _augment_question(question, selected_title)
                else:
                    agent = build_base_agent()
                    prompt = question
                answer = agent(prompt)
                st.markdown(str(answer))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Agent call failed: {type(exc).__name__}: {exc}")
                answer = None

        # Source panel: for the enhanced mode, show a direct read of the chosen
        # document so the user sees exactly what evidence was available.
        if mode.startswith("After") and answer is not None:
            key = config.key_for_title(selected_title)
            result = read_document(key) if key else None
            with col_src:
                src_placeholder.empty()
                st.subheader("Source")
                if result is None:
                    st.warning("No source document resolved.")
                elif result.ok:
                    st.success(f"**Document:** {selected_title}")
                    st.write(f"**Key:** `{result.key}`")
                    st.write(f"**Pages:** {result.pages}")
                    if result.truncated:
                        st.caption("Note: document text was truncated for length.")
                    with st.expander("Preview extracted text"):
                        st.text(result.text[:2000])
                else:
                    st.warning(
                        f"Document could not be read "
                        f"(`{result.error_type}`): {result.error}"
                    )
        elif mode.startswith("Before"):
            with col_src:
                src_placeholder.empty()
                st.subheader("Source")
                st.info(
                    "Before mode: the original agent has no document access, so "
                    "there are no document sources. Switch to After mode to read "
                    "from Amazon S3."
                )
