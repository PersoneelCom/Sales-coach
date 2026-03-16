from __future__ import annotations

import unittest

from services.transcript_utils import format_timestamp, merge_segments_into_transcript


class FormatTimestampTests(unittest.TestCase):
    def test_returns_empty_string_for_none(self) -> None:
        self.assertEqual(format_timestamp(None), "")

    def test_formats_minutes_and_seconds(self) -> None:
        self.assertEqual(format_timestamp(65), "01:05")

    def test_formats_hours_when_needed(self) -> None:
        self.assertEqual(format_timestamp(3661), "01:01:01")


class MergeSegmentsTests(unittest.TestCase):
    def test_prefers_segments_and_normalizes_speakers(self) -> None:
        payload = {
            "language": "nl",
            "duration": 90,
            "segments": [
                {"start": 0, "end": 5, "speaker": "", "text": " Hallo "},
                {"start_time": 5, "end_time": 8, "speaker_label": "speaker_9", "transcript": "World"},
                {"start": 8, "end": 10, "label": "Agent", "text": "Done"},
            ],
        }

        result = merge_segments_into_transcript(payload)

        self.assertEqual(result["language"], "nl")
        self.assertEqual(result["duration_seconds"], 90)
        self.assertEqual(
            result["segments"],
            [
                {
                    "speaker": "Speaker 1",
                    "text": "Hallo",
                    "start_seconds": None,
                    "end_seconds": 5,
                    "start_label": "",
                    "end_label": "00:05",
                },
                {
                    "speaker": "Speaker 9",
                    "text": "World",
                    "start_seconds": 5,
                    "end_seconds": 8,
                    "start_label": "00:05",
                    "end_label": "00:08",
                },
                {
                    "speaker": "Agent",
                    "text": "Done",
                    "start_seconds": 8,
                    "end_seconds": 10,
                    "start_label": "00:08",
                    "end_label": "00:10",
                },
            ],
        )
        self.assertEqual(result["full_text"], "Speaker 1: Hallo\nSpeaker 9: World\nAgent: Done")

    def test_uses_fallback_text_when_segments_missing(self) -> None:
        payload = {
            "text": " Full transcript ",
            "duration": 125,
        }

        result = merge_segments_into_transcript(payload)

        self.assertEqual(result["language"], "unknown")
        self.assertEqual(result["segments"][0]["speaker"], "Speaker 1")
        self.assertEqual(result["segments"][0]["text"], "Full transcript")
        self.assertEqual(result["segments"][0]["start_label"], "00:00")
        self.assertEqual(result["segments"][0]["end_label"], "02:05")

    def test_skips_empty_segments_and_uses_alternate_segment_lists(self) -> None:
        payload = {
            "speaker_segments": [
                {"speaker": None, "text": "   "},
                {"speaker": "speaker", "text": "Kept", "start": 1, "end": 2},
            ]
        }

        result = merge_segments_into_transcript(payload)

        self.assertEqual(len(result["segments"]), 1)
        self.assertEqual(result["segments"][0]["speaker"], "Speaker 2")
        self.assertEqual(result["segments"][0]["text"], "Kept")


if __name__ == "__main__":
    unittest.main()
