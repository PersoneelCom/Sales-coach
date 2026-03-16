from __future__ import annotations

from typing import Any


def format_timestamp(seconds: float | int | None) -> str:
    if seconds is None:
        return ""

    total_seconds = int(float(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _normalize_speaker(raw_value: Any, index: int) -> str:
    if raw_value in (None, "", "speaker"):
        return f"Speaker {1 if index % 2 == 0 else 2}"

    speaker_text = str(raw_value).strip()
    if speaker_text.lower().startswith("speaker"):
        number = "".join(ch for ch in speaker_text if ch.isdigit())
        if number:
            return f"Speaker {number}"
    return speaker_text


def merge_segments_into_transcript(payload: dict) -> dict:
    raw_segments = (
        payload.get("segments")
        or payload.get("speaker_segments")
        or payload.get("diarization")
        or []
    )
    segments = []

    for index, segment in enumerate(raw_segments):
        start = segment.get("start") or segment.get("start_time")
        end = segment.get("end") or segment.get("end_time")
        speaker = _normalize_speaker(
            segment.get("speaker") or segment.get("speaker_label") or segment.get("label"),
            index,
        )
        text = (segment.get("text") or segment.get("transcript") or "").strip()

        if not text:
            continue

        segments.append(
            {
                "speaker": speaker,
                "text": text,
                "start_seconds": start,
                "end_seconds": end,
                "start_label": format_timestamp(start),
                "end_label": format_timestamp(end),
            }
        )

    if not segments and payload.get("text"):
        segments.append(
            {
                "speaker": "Speaker 1",
                "text": payload["text"].strip(),
                "start_seconds": 0,
                "end_seconds": payload.get("duration"),
                "start_label": "00:00",
                "end_label": format_timestamp(payload.get("duration")),
            }
        )

    return {
        "language": payload.get("language", "unknown"),
        "duration_seconds": payload.get("duration"),
        "segments": segments,
        "full_text": "\n".join(f"{segment['speaker']}: {segment['text']}" for segment in segments),
    }
