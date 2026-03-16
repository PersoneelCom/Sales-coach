import json
import logging
import os
from datetime import UTC, datetime
from typing import Optional

import streamlit as st

from services.config import get_setting
from services.google_docs import GoogleDocsExporter, GoogleDocsSetupError
from services.openai_service import OpenAISetupError, summarize_call, transcribe_call
from services.pdf_export import build_transcript_pdf
from services.security import (
    SecurityValidationError,
    coerce_bool,
    coerce_int,
    seconds_until_allowed,
    validate_wav_upload,
    verify_password,
)


st.set_page_config(page_title="Sales Coach", layout="wide")

logger = logging.getLogger(__name__)

AUTH_REQUIRED = coerce_bool(get_setting("AUTH_REQUIRED", "true"), default=True)
ALLOW_GOOGLE_EXPORT = coerce_bool(get_setting("ALLOW_GOOGLE_EXPORT", "true"), default=True)
APP_PASSWORD_HASH = get_setting("APP_PASSWORD_HASH")
MAX_UPLOAD_MB = coerce_int(get_setting("MAX_UPLOAD_MB", 25), default=25, minimum=1)
MAX_AUDIO_MINUTES = coerce_int(get_setting("MAX_AUDIO_MINUTES", 30), default=30, minimum=1)
PROCESS_COOLDOWN_SECONDS = coerce_int(
    get_setting("PROCESS_COOLDOWN_SECONDS", 60),
    default=60,
    minimum=0,
)

if "processed_call" not in st.session_state:
    st.session_state.processed_call = None
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False
if "last_submission_at" not in st.session_state:
    st.session_state.last_submission_at = None


def _rename_speakers(transcript: dict, speaker_one_name: str, speaker_two_name: str) -> dict:
    renamed_segments = []
    for segment in transcript["segments"]:
        label = segment["speaker"]
        if label == "Speaker 1":
            label = speaker_one_name
        elif label == "Speaker 2":
            label = speaker_two_name

        renamed_segments.append({**segment, "speaker": label})

    return {**transcript, "segments": renamed_segments}


def _build_google_export(
    file_name: str,
    summary_markdown: str,
    transcript: dict,
) -> Optional[str]:
    try:
        exporter = GoogleDocsExporter()
    except GoogleDocsSetupError as exc:
        st.warning(str(exc))
        return None

    try:
        return exporter.create_document(
            title=f"Sales Coach - {file_name}",
            summary_markdown=summary_markdown,
            transcript=transcript,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Google Docs export failed")
        st.error("Google Docs export failed. Please try again later.")
        return None


def _render_access_gate() -> bool:
    if not AUTH_REQUIRED:
        return True
    if st.session_state.is_authenticated:
        return True

    st.subheader("Restricted Access")
    st.caption("This app processes customer call data. Authentication is required.")

    if not APP_PASSWORD_HASH:
        st.error("Missing APP_PASSWORD_HASH. Configure a password hash before exposing this app.")
        return False

    with st.form("login_form", clear_on_submit=True):
        password = st.text_input("Access password", type="password")
        submitted = st.form_submit_button("Unlock")

    if submitted:
        if verify_password(password, APP_PASSWORD_HASH):
            st.session_state.is_authenticated = True
            st.rerun()
        st.error("Invalid password.")

    return False


st.title("Sales Coach")
st.caption("Upload a sales call, generate a summary, and export the transcript to Google Docs or PDF.")

with st.sidebar:
    st.subheader("How this MVP works")
    st.write("1. Upload one WAV file.")
    st.write("2. Transcribe with speaker labels.")
    st.write("3. Rename Speaker 1 and Speaker 2.")
    st.write("4. Generate a summary.")
    st.write("5. Export to Google Docs or PDF.")

    st.subheader("Before first use")
    st.write("Add your secrets in a local `.env` file or Streamlit secrets.")
    st.write("Google Docs export needs a Google service account JSON credential.")
    st.subheader("Security defaults")
    st.write(f"Authentication required: {'Yes' if AUTH_REQUIRED else 'No'}")
    st.write(f"Max upload size: {MAX_UPLOAD_MB} MB")
    st.write(f"Max audio length: {MAX_AUDIO_MINUTES} minutes")
    st.write(f"Cooldown between jobs: {PROCESS_COOLDOWN_SECONDS} seconds")
    if AUTH_REQUIRED and st.session_state.is_authenticated and st.button("Sign out"):
        st.session_state.is_authenticated = False
        st.session_state.processed_call = None
        st.rerun()

if not _render_access_gate():
    st.stop()


uploaded_file = st.file_uploader("Upload a WAV sales call", type=["wav"])

speaker_one_name = st.text_input("Rename Speaker 1", value="You")
speaker_two_name = st.text_input("Rename Speaker 2", value="Prospect")
authorization_confirmed = st.checkbox(
    "I confirm I am authorized to process this call and send it to OpenAI for transcription and summarization.",
    value=False,
)
generate_clicked = st.button(
    "Process call",
    type="primary",
    disabled=uploaded_file is None or not authorization_confirmed,
)

if generate_clicked and uploaded_file is not None:
    if not authorization_confirmed:
        st.error("Confirm that you are authorized to process this call before continuing.")
        st.stop()

    file_name = os.path.basename(uploaded_file.name)
    max_size_bytes = MAX_UPLOAD_MB * 1024 * 1024
    max_duration_seconds = MAX_AUDIO_MINUTES * 60
    uploaded_size = getattr(uploaded_file, "size", None)
    if isinstance(uploaded_size, int) and uploaded_size > max_size_bytes:
        st.error(f"File is too large. The limit is {MAX_UPLOAD_MB} MB.")
        st.stop()

    remaining_seconds = seconds_until_allowed(
        st.session_state.last_submission_at,
        datetime.now(UTC),
        cooldown_seconds=PROCESS_COOLDOWN_SECONDS,
    )
    if remaining_seconds:
        st.error(f"Please wait {remaining_seconds} seconds before processing another call.")
        st.stop()

    audio_bytes = uploaded_file.getvalue()
    try:
        validate_wav_upload(
            file_name=file_name,
            audio_bytes=audio_bytes,
            max_size_bytes=max_size_bytes,
            max_duration_seconds=max_duration_seconds,
        )
    except SecurityValidationError as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.last_submission_at = datetime.now(UTC)

    with st.spinner("Transcribing the call..."):
        try:
            transcript = transcribe_call(file_name, audio_bytes)
        except OpenAISetupError as exc:
            st.error(str(exc))
            st.stop()
        except Exception:  # noqa: BLE001
            logger.exception("Transcription failed")
            st.error("Transcription failed. Please try again later.")
            st.stop()

    renamed_transcript = _rename_speakers(transcript, speaker_one_name, speaker_two_name)

    with st.spinner("Generating the summary..."):
        try:
            summary_markdown = summarize_call(renamed_transcript)
        except OpenAISetupError as exc:
            st.error(str(exc))
            st.stop()
        except Exception:  # noqa: BLE001
            logger.exception("Summary generation failed")
            st.error("Summary generation failed. Please try again later.")
            st.stop()

    st.session_state.processed_call = {
        "file_name": file_name,
        "transcript": renamed_transcript,
        "summary_markdown": summary_markdown,
    }
    st.success("Call processed.")

processed_call = st.session_state.processed_call

if processed_call:
    file_name = processed_call["file_name"]
    renamed_transcript = processed_call["transcript"]
    summary_markdown = processed_call["summary_markdown"]

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Summary")
        st.markdown(summary_markdown)

    with col2:
        st.subheader("Transcript data")
        st.json(
            {
                "language": renamed_transcript["language"],
                "duration_seconds": renamed_transcript["duration_seconds"],
                "segment_count": len(renamed_transcript["segments"]),
            }
        )

    st.subheader("Transcript")
    for segment in renamed_transcript["segments"]:
        heading = f"**{segment['speaker']}**"
        if segment.get("start_label"):
            heading += f" `{segment['start_label']}`"
        st.markdown(heading)
        st.write(segment["text"])

    pdf_bytes = build_transcript_pdf(
        title=f"Sales Coach - {file_name}",
        summary_markdown=summary_markdown,
        transcript=renamed_transcript,
    )
    st.download_button(
        label="Download PDF",
        data=pdf_bytes,
        file_name=f"{file_name.rsplit('.', 1)[0]}-sales-coach.pdf",
        mime="application/pdf",
    )

    if ALLOW_GOOGLE_EXPORT and st.button("Export to Google Docs"):
        with st.spinner("Creating Google Doc..."):
            document_url = _build_google_export(file_name, summary_markdown, renamed_transcript)
        if document_url:
            st.success(f"Google Doc created: {document_url}")
    elif not ALLOW_GOOGLE_EXPORT:
        st.info("Google Docs export is disabled in this environment.")

    with st.expander("Raw transcript JSON"):
        st.code(json.dumps(renamed_transcript, indent=2), language="json")
