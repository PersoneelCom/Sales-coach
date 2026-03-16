import json
import logging
import os
from datetime import UTC, datetime
from html import escape
from typing import Optional

import streamlit as st

from services.analysis_utils import extract_first_bullet, extract_score_value, split_markdown_sections
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
from services.storage import load_call_history, save_call_record


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


def _build_google_export(file_name: str, summary_markdown: str, transcript: dict) -> Optional[str]:
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
    st.caption("This app processes call data. Authentication is required.")

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


def _render_metric_card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{escape(label)}</div><div class="metric-value">{escape(value)}</div></div>',
        unsafe_allow_html=True,
    )


def _save_processed_call(file_name: str, transcript: dict, summary_markdown: str) -> None:
    sections = split_markdown_sections(summary_markdown)
    save_call_record(
        {
            "file_name": file_name,
            "call_type": sections.get("Call Type", "Unknown"),
            "score": extract_score_value(sections.get("Call Score", "")),
            "top_objection": extract_first_bullet(sections.get("Objections", "")),
            "next_step": extract_first_bullet(sections.get("Next Steps", "")),
            "language": transcript["language"],
            "duration_seconds": transcript["duration_seconds"],
            "segment_count": len(transcript["segments"]),
        }
    )


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

    :root {
        --bg: #f5ecdf;
        --panel: rgba(255, 252, 247, 0.9);
        --panel-alt: rgba(255, 245, 232, 0.88);
        --text: #1e1c1a;
        --muted: #726759;
        --line: rgba(38, 27, 17, 0.08);
        --accent: #b55a34;
        --accent-2: #204f5a;
        --accent-dark: #8a4023;
        --shadow: 0 24px 60px rgba(65, 40, 14, 0.10);
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 15%, rgba(181, 90, 52, 0.16), transparent 22%),
            radial-gradient(circle at 85% 8%, rgba(32, 79, 90, 0.12), transparent 18%),
            linear-gradient(180deg, #fbf5ed 0%, var(--bg) 100%);
        color: var(--text);
        font-family: "Manrope", sans-serif;
    }

    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3rem;
        max-width: 1220px;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at top, rgba(181, 90, 52, 0.18), transparent 28%),
            linear-gradient(180deg, #1a1c20 0%, #23242a 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }

    [data-testid="stSidebar"] * {
        color: #f7f4ef;
    }

    @keyframes riseIn {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes floatBlob {
        0% { transform: translateY(0px) translateX(0px); }
        50% { transform: translateY(-10px) translateX(6px); }
        100% { transform: translateY(0px) translateX(0px); }
    }

    @keyframes pulseGlow {
        0% { box-shadow: 0 0 0 rgba(181, 90, 52, 0.0); }
        50% { box-shadow: 0 0 40px rgba(181, 90, 52, 0.10); }
        100% { box-shadow: 0 0 0 rgba(181, 90, 52, 0.0); }
    }

    .hero {
        position: relative;
        overflow: hidden;
        padding: 2.3rem 2.4rem;
        border-radius: 32px;
        background: linear-gradient(145deg, rgba(255, 252, 247, 0.98), rgba(248, 236, 219, 0.9));
        box-shadow: var(--shadow);
        border: 1px solid rgba(181, 82, 51, 0.10);
        margin-bottom: 1.3rem;
        animation: riseIn 0.55s ease-out both, pulseGlow 6s ease-in-out infinite;
    }

    .hero::before,
    .hero::after {
        content: "";
        position: absolute;
        border-radius: 999px;
        filter: blur(6px);
        animation: floatBlob 8s ease-in-out infinite;
    }

    .hero::before {
        width: 180px;
        height: 180px;
        background: rgba(181, 90, 52, 0.12);
        top: -60px;
        right: 8%;
    }

    .hero::after {
        width: 120px;
        height: 120px;
        background: rgba(32, 79, 90, 0.12);
        bottom: -30px;
        right: 22%;
        animation-delay: 1s;
    }

    .eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: var(--accent);
        font-size: 0.75rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }

    .hero h1 {
        margin: 0;
        font-family: "Fraunces", serif;
        font-size: 4rem;
        line-height: 0.92;
        letter-spacing: -0.04em;
        position: relative;
        z-index: 1;
    }

    .hero p {
        margin: 0.9rem 0 0;
        max-width: 700px;
        font-size: 1.08rem;
        color: var(--muted);
        position: relative;
        z-index: 1;
    }

    .hero-grid {
        display: grid;
        grid-template-columns: 1.45fr 0.85fr;
        gap: 1rem;
        align-items: end;
        position: relative;
        z-index: 1;
    }

    .hero-note {
        justify-self: end;
        background: rgba(255, 255, 255, 0.66);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(38, 27, 17, 0.08);
        border-radius: 22px;
        padding: 1rem 1rem 0.9rem;
        min-width: 240px;
    }

    .hero-note-label {
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 0.35rem;
    }

    .hero-note-value {
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }

    .card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 26px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
        padding: 1.2rem 1.2rem 1rem;
        animation: riseIn 0.45s ease-out both;
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(255, 248, 239, 0.95), rgba(255, 252, 247, 0.82));
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1rem 1.1rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
    }

    .metric-label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
    }

    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin-top: 0.2rem;
    }

    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 0.9rem;
        letter-spacing: -0.02em;
    }

    .subtle-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
        margin-bottom: 0.4rem;
    }

    .transcript-card {
        background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(251, 244, 234, 0.92));
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1rem 1rem 0.85rem;
        margin-bottom: 0.8rem;
        transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }

    .transcript-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 18px 32px rgba(65, 40, 14, 0.08);
        border-color: rgba(181, 90, 52, 0.18);
    }

    .transcript-meta {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        margin-bottom: 0.4rem;
    }

    .speaker-chip {
        display: inline-block;
        background: linear-gradient(135deg, rgba(181, 82, 51, 0.16), rgba(181, 82, 51, 0.08));
        color: var(--accent-dark);
        border-radius: 999px;
        padding: 0.32rem 0.72rem;
        font-size: 0.84rem;
        font-weight: 700;
    }

    .time-chip {
        color: var(--muted);
        font-size: 0.82rem;
    }

    .summary-box h2 {
        margin-top: 1.3rem;
        font-size: 1.05rem;
        font-family: "Fraunces", serif;
    }

    .summary-box ul {
        padding-left: 1.2rem;
    }

    .summary-box p,
    .summary-box li,
    .transcript-card div {
        line-height: 1.6;
    }

    .signal-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
        margin-bottom: 1rem;
    }

    .signal-panel {
        background: rgba(255,255,255,0.56);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 0.95rem 1rem;
    }

    .signal-panel-title {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
        margin-bottom: 0.3rem;
    }

    .signal-panel-copy {
        font-size: 0.98rem;
        font-weight: 600;
    }

    .history-item {
        background: rgba(255,255,255,0.58);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 0.95rem 1rem;
        margin-bottom: 0.75rem;
    }

    .history-title {
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .history-meta {
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 0.45rem;
    }

    .pill-row {
        display: flex;
        gap: 0.45rem;
        flex-wrap: wrap;
        margin: 0.55rem 0 0.75rem;
    }

    .pill {
        display: inline-block;
        padding: 0.4rem 0.7rem;
        border-radius: 999px;
        background: rgba(32, 79, 90, 0.08);
        color: var(--accent-2);
        font-size: 0.84rem;
        font-weight: 700;
    }

    .summary-hero {
        margin-bottom: 1rem;
        background: linear-gradient(135deg, rgba(181, 90, 52, 0.10), rgba(32, 79, 90, 0.08));
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1rem 1rem 0.95rem;
    }

    .summary-title {
        font-family: "Fraunces", serif;
        font-size: 1.5rem;
        line-height: 1;
        margin-bottom: 0.35rem;
    }

    .split-grid {
        display: grid;
        grid-template-columns: 1.35fr 0.9fr;
        gap: 1rem;
    }

    .mini-stat {
        display: grid;
        gap: 0.25rem;
        background: rgba(255,255,255,0.54);
        border-radius: 16px;
        padding: 0.9rem;
        border: 1px solid var(--line);
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 999px;
        border: none;
        background: linear-gradient(135deg, var(--accent) 0%, #cc734f 100%);
        color: white;
        font-weight: 700;
        padding: 0.72rem 1.05rem;
        box-shadow: 0 10px 20px rgba(181, 90, 52, 0.2);
        transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background: var(--accent-dark);
        color: white;
        transform: translateY(-1px);
        box-shadow: 0 16px 28px rgba(181, 90, 52, 0.24);
    }

    [data-baseweb="tab-list"] {
        gap: 0.4rem;
        margin-top: 0.7rem;
    }

    [data-baseweb="tab"] {
        background: rgba(255,255,255,0.58);
        border-radius: 999px;
        border: 1px solid var(--line);
        padding: 0.5rem 0.9rem;
    }

    [data-baseweb="tab-highlight"] {
        background: linear-gradient(135deg, rgba(181, 90, 52, 0.15), rgba(32, 79, 90, 0.10));
        border-radius: 999px;
    }

    @media (max-width: 900px) {
        .hero-grid {
            grid-template-columns: 1fr;
        }

        .hero-note {
            justify-self: start;
            min-width: 0;
        }

        .signal-strip,
        .split-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <div class="hero-grid">
            <div>
                <div class="eyebrow">Sales Call Intelligence</div>
                <h1>Sales Coach</h1>
                <p>Upload a WAV file, separate the speakers, surface objections and buying questions, and turn every call into a clean coaching document.</p>
            </div>
            <div class="hero-note">
                <div class="hero-note-label">Built for review</div>
                <div class="hero-note-value">Questions. Objections. Signals.</div>
                <div>Designed to help you spot what moved the deal and what stalled it.</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Sales Coach")
    st.caption("Single-user MVP for call review.")
    st.markdown("### Workflow")
    st.write("1. Upload one WAV file")
    st.write("2. Rename both speakers")
    st.write("3. Process the call")
    st.write("4. Review questions, objections, and next steps")
    st.write("5. Export to PDF or Google Docs")
    st.markdown("### Setup")
    st.write("Use `.env` for local secrets.")
    st.write("Google Docs export needs a service account JSON.")
    st.markdown("### Focus")
    st.write("Modern SaaS coaching tool for internal sales improvement.")
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

history = load_call_history()

control_col, info_col = st.columns([1.2, 0.8], gap="large")

with control_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Process a Call</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload a WAV sales call", type=["wav"], label_visibility="visible")
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
    st.markdown("</div>", unsafe_allow_html=True)

with info_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">What You Get</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="signal-strip">
            <div class="signal-panel">
                <div class="signal-panel-title">Coach View</div>
                <div class="signal-panel-copy">Questions, objections, and momentum in one place.</div>
            </div>
            <div class="signal-panel">
                <div class="signal-panel-title">Transcript</div>
                <div class="signal-panel-copy">Readable speaker-by-speaker timeline.</div>
            </div>
            <div class="signal-panel">
                <div class="signal-panel-title">Exports</div>
                <div class="signal-panel-copy">Send clean notes to Docs or PDF fast.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

history_col, latest_col = st.columns([0.85, 1.15], gap="large")

with history_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Call History</div>', unsafe_allow_html=True)
    if history:
        for item in history[:6]:
            score_value = f"{item['score']}/10" if item.get("score") is not None else "No score"
            next_step = escape(item.get("next_step") or "No next step captured")
            top_objection = escape(item.get("top_objection") or "No objection captured")
            st.markdown(
                f"""
                <div class="history-item">
                    <div class="history-title">{escape(item['file_name'])}</div>
                    <div class="history-meta">{escape(item.get('call_type') or 'Unknown')} · {score_value}</div>
                    <div><strong>Objection:</strong> {top_objection}</div>
                    <div><strong>Next step:</strong> {next_step}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.write("No saved calls yet. Process your first WAV file to build a coaching history.")
    st.markdown("</div>", unsafe_allow_html=True)

with latest_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Analysis Focus</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="split-grid">
            <div class="mini-stat">
                <div class="subtle-label">What this version is built to surface</div>
                <div>Conversation structure, questions asked, objections, coaching feedback, and a clear score out of 10.</div>
            </div>
            <div class="mini-stat">
                <div class="subtle-label">Current product scope</div>
                <div>Internal single-user coaching tool now, with a path toward a SaaS product later.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

if generate_clicked and uploaded_file is not None:
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
    _save_processed_call(file_name, renamed_transcript, summary_markdown)
    st.success("Call processed.")

processed_call = st.session_state.processed_call

if processed_call:
    file_name = processed_call["file_name"]
    renamed_transcript = processed_call["transcript"]
    summary_markdown = processed_call["summary_markdown"]
    sections = split_markdown_sections(summary_markdown)
    score_value = extract_score_value(sections.get("Call Score", ""))
    call_type = sections.get("Call Type", "Unknown")

    stats_col1, stats_col2, stats_col3 = st.columns(3, gap="medium")
    with stats_col1:
        _render_metric_card("Call Type", call_type)
    with stats_col2:
        score_display = f"{score_value}/10" if score_value is not None else "Pending"
        _render_metric_card("Call Score", score_display)
    with stats_col3:
        duration = renamed_transcript["duration_seconds"] or 0
        _render_metric_card("Duration", f"{round(duration / 60, 1)} min")

    summary_tab, transcript_tab, export_tab, debug_tab = st.tabs(["Summary", "Transcript", "Exports", "Debug"])

    with summary_tab:
        st.markdown('<div class="card summary-box">', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="summary-hero">
                <div class="subtle-label">Current analysis</div>
                <div class="summary-title">{escape(call_type)}</div>
                <div class="pill-row">
                    <span class="pill">{escape(renamed_transcript['language'])}</span>
                    <span class="pill">{len(renamed_transcript['segments'])} segments</span>
                    <span class="pill">{(str(score_value) + '/10') if score_value is not None else 'score pending'}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(summary_markdown)
        st.markdown("</div>", unsafe_allow_html=True)

    with transcript_tab:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Full Transcript</div>', unsafe_allow_html=True)
        for segment in renamed_transcript["segments"]:
            speaker = escape(segment["speaker"])
            timestamp = escape(segment["start_label"])
            body = escape(segment["text"])
            st.markdown(
                f"""
                <div class="transcript-card">
                    <div class="transcript-meta">
                        <span class="speaker-chip">{speaker}</span>
                        <span class="time-chip">{timestamp}</span>
                    </div>
                    <div>{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    pdf_bytes = build_transcript_pdf(
        title=f"Sales Coach - {file_name}",
        summary_markdown=summary_markdown,
        transcript=renamed_transcript,
    )

    with export_tab:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Exports</div>', unsafe_allow_html=True)
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=f"{file_name.rsplit('.', 1)[0]}-sales-coach.pdf",
            mime="application/pdf",
        )
        if ALLOW_GOOGLE_EXPORT:
            if st.button("Export to Google Docs"):
                with st.spinner("Creating Google Doc..."):
                    document_url = _build_google_export(file_name, summary_markdown, renamed_transcript)
                if document_url:
                    st.success(f"Google Doc created: {document_url}")
        else:
            st.info("Google Docs export is disabled in this environment.")
        st.markdown("</div>", unsafe_allow_html=True)

    with debug_tab:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.json(
            {
                "language": renamed_transcript["language"],
                "duration_seconds": renamed_transcript["duration_seconds"],
                "segment_count": len(renamed_transcript["segments"]),
            }
        )
        st.code(json.dumps(renamed_transcript, indent=2), language="json")
        st.markdown("</div>", unsafe_allow_html=True)
