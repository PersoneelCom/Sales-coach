from __future__ import annotations

import io
from typing import Any

from openai import OpenAI

from services.config import get_setting
from services.transcript_utils import merge_segments_into_transcript


class OpenAISetupError(RuntimeError):
    pass


def _get_client() -> OpenAI:
    api_key = get_setting("OPENAI_API_KEY")
    if not api_key:
        raise OpenAISetupError(
            "Missing OPENAI_API_KEY. Add it to your `.env` file or Streamlit secrets before processing calls."
        )
    return OpenAI(api_key=api_key)


def _to_dict(data: Any) -> dict:
    if isinstance(data, dict):
        return data
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return dict(data)


def transcribe_call(file_name: str, audio_bytes: bytes) -> dict:
    client = _get_client()
    model = get_setting("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize")
    response_format = "diarized_json" if "diarize" in model else "json"

    audio_stream = io.BytesIO(audio_bytes)
    audio_stream.name = file_name

    request_kwargs = {
        "model": model,
        "file": audio_stream,
        "response_format": response_format,
    }
    if "diarize" in model:
        request_kwargs["chunking_strategy"] = "auto"

    response = client.audio.transcriptions.create(**request_kwargs)
    payload = _to_dict(response)
    return merge_segments_into_transcript(payload)


def summarize_call(transcript: dict) -> str:
    client = _get_client()
    model = get_setting("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")

    transcript_text = []
    for segment in transcript["segments"]:
        line = f"{segment['speaker']} [{segment['start_label']}]: {segment['text']}"
        transcript_text.append(line)

    prompt = """
You are analyzing a sales call transcript.

Write clean markdown with these exact sections:
## Call Summary
## Key Pain Points
## Objections
## Next Steps

Rules:
- Keep it concise and useful for a salesperson.
- Mention both Dutch and English content naturally if present.
- Use bullet points where useful.
- Do not invent facts that are not in the transcript.
"""

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": "\n".join(transcript_text),
            },
        ],
    )

    return response.output_text
