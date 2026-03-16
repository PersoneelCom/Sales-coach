import json
from typing import Optional

import streamlit as st

from services.google_docs import GoogleDocsExporter, GoogleDocsSetupError
from services.openai_service import OpenAISetupError, summarize_call, transcribe_call
from services.pdf_export import build_transcript_pdf


st.set_page_config(page_title="Sales Coach", layout="wide")

if "processed_call" not in st.session_state:
    st.session_state.processed_call = None


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

    return exporter.create_document(
        title=f"Sales Coach - {file_name}",
        summary_markdown=summary_markdown,
        transcript=transcript,
    )


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
    st.write("Add your API keys in a local `.env` file or Streamlit secrets.")
    st.write("Google Docs export needs a Google service account JSON credential.")


uploaded_file = st.file_uploader("Upload a WAV sales call", type=["wav"])

speaker_one_name = st.text_input("Rename Speaker 1", value="You")
speaker_two_name = st.text_input("Rename Speaker 2", value="Prospect")
generate_clicked = st.button("Process call", type="primary", disabled=uploaded_file is None)

if generate_clicked and uploaded_file is not None:
    with st.spinner("Transcribing the call..."):
        try:
            transcript = transcribe_call(uploaded_file.name, uploaded_file.getvalue())
        except OpenAISetupError as exc:
            st.error(str(exc))
            st.stop()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Transcription failed: {exc}")
            st.stop()

    renamed_transcript = _rename_speakers(transcript, speaker_one_name, speaker_two_name)

    with st.spinner("Generating the summary..."):
        try:
            summary_markdown = summarize_call(renamed_transcript)
        except OpenAISetupError as exc:
            st.error(str(exc))
            st.stop()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Summary generation failed: {exc}")
            st.stop()

    st.session_state.processed_call = {
        "file_name": uploaded_file.name,
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

    if st.button("Export to Google Docs"):
        with st.spinner("Creating Google Doc..."):
            document_url = _build_google_export(file_name, summary_markdown, renamed_transcript)
        if document_url:
            st.success(f"Google Doc created: {document_url}")

    with st.expander("Raw transcript JSON"):
        st.code(json.dumps(renamed_transcript, indent=2), language="json")
