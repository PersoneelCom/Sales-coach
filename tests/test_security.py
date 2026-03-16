from __future__ import annotations

import io
import unittest
import wave
from datetime import UTC, datetime, timedelta

from services.security import (
    SecurityValidationError,
    build_password_hash,
    coerce_bool,
    coerce_int,
    seconds_until_allowed,
    validate_wav_upload,
    verify_password,
)


def _make_wav_bytes(duration_seconds: float, sample_rate: int = 8000) -> bytes:
    frame_count = int(duration_seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


class PasswordHashTests(unittest.TestCase):
    def test_verify_password_accepts_matching_secret(self) -> None:
        encoded = build_password_hash("correct horse battery staple")
        self.assertTrue(verify_password("correct horse battery staple", encoded))

    def test_verify_password_rejects_wrong_secret(self) -> None:
        encoded = build_password_hash("correct horse battery staple")
        self.assertFalse(verify_password("wrong secret", encoded))

    def test_verify_password_rejects_invalid_hash_format(self) -> None:
        self.assertFalse(verify_password("anything", "not-a-valid-hash"))


class ConfigParsingTests(unittest.TestCase):
    def test_coerce_bool_accepts_common_truthy_values(self) -> None:
        self.assertTrue(coerce_bool("true", default=False))
        self.assertTrue(coerce_bool("1", default=False))
        self.assertTrue(coerce_bool("yes", default=False))

    def test_coerce_bool_accepts_common_falsey_values(self) -> None:
        self.assertFalse(coerce_bool("false", default=True))
        self.assertFalse(coerce_bool("0", default=True))
        self.assertFalse(coerce_bool("no", default=True))

    def test_coerce_bool_falls_back_to_default_for_unknown_values(self) -> None:
        self.assertTrue(coerce_bool("not-sure", default=True))

    def test_coerce_int_returns_default_for_invalid_values(self) -> None:
        self.assertEqual(coerce_int("invalid", default=25, minimum=1), 25)
        self.assertEqual(coerce_int("-10", default=25, minimum=1), 25)

    def test_coerce_int_returns_parsed_value_when_valid(self) -> None:
        self.assertEqual(coerce_int("50", default=25, minimum=1), 50)


class UploadValidationTests(unittest.TestCase):
    def test_validate_wav_upload_accepts_valid_wav(self) -> None:
        audio_bytes = _make_wav_bytes(duration_seconds=2)

        result = validate_wav_upload(
            file_name="call.wav",
            audio_bytes=audio_bytes,
            max_size_bytes=len(audio_bytes) + 10,
            max_duration_seconds=10,
        )

        self.assertEqual(result.size_bytes, len(audio_bytes))
        self.assertAlmostEqual(result.duration_seconds, 2.0, places=1)

    def test_validate_wav_upload_rejects_non_wav_extension(self) -> None:
        with self.assertRaisesRegex(SecurityValidationError, "WAV files"):
            validate_wav_upload(
                file_name="call.mp3",
                audio_bytes=b"fake",
                max_size_bytes=1024,
                max_duration_seconds=60,
            )

    def test_validate_wav_upload_rejects_invalid_wav_content(self) -> None:
        with self.assertRaisesRegex(SecurityValidationError, "valid WAV"):
            validate_wav_upload(
                file_name="call.wav",
                audio_bytes=b"not really a wav",
                max_size_bytes=1024,
                max_duration_seconds=60,
            )

    def test_validate_wav_upload_rejects_large_files(self) -> None:
        audio_bytes = _make_wav_bytes(duration_seconds=2)

        with self.assertRaisesRegex(SecurityValidationError, "too large"):
            validate_wav_upload(
                file_name="call.wav",
                audio_bytes=audio_bytes,
                max_size_bytes=len(audio_bytes) - 1,
                max_duration_seconds=60,
            )

    def test_validate_wav_upload_rejects_long_audio(self) -> None:
        audio_bytes = _make_wav_bytes(duration_seconds=120)

        with self.assertRaisesRegex(SecurityValidationError, "too long"):
            validate_wav_upload(
                file_name="call.wav",
                audio_bytes=audio_bytes,
                max_size_bytes=len(audio_bytes) + 10,
                max_duration_seconds=60,
            )


class CooldownTests(unittest.TestCase):
    def test_seconds_until_allowed_returns_zero_when_no_previous_attempt(self) -> None:
        now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        self.assertEqual(seconds_until_allowed(None, now, cooldown_seconds=60), 0)

    def test_seconds_until_allowed_returns_remaining_seconds(self) -> None:
        now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        last_processed_at = now - timedelta(seconds=15)
        self.assertEqual(seconds_until_allowed(last_processed_at, now, cooldown_seconds=60), 45)

    def test_seconds_until_allowed_returns_zero_after_window_expires(self) -> None:
        now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        last_processed_at = now - timedelta(seconds=75)
        self.assertEqual(seconds_until_allowed(last_processed_at, now, cooldown_seconds=60), 0)


if __name__ == "__main__":
    unittest.main()
