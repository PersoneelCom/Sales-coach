from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import wave
from dataclasses import dataclass
from datetime import datetime


PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390000


class SecurityValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AudioValidationResult:
    duration_seconds: float
    size_bytes: int


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def build_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(derived_key)}"


def coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def coerce_int(value: object, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (AttributeError, TypeError, ValueError):
        return default

    if minimum is not None and parsed < minimum:
        return default
    return parsed


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, expected_text = encoded_hash.split("$", 3)
        if algorithm != PBKDF2_ALGORITHM:
            return False
        iterations = int(iteration_text)
        salt = _b64decode(salt_text)
        expected_hash = _b64decode(expected_text)
    except (ValueError, TypeError, base64.binascii.Error):
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def validate_wav_upload(
    file_name: str,
    audio_bytes: bytes,
    max_size_bytes: int,
    max_duration_seconds: int,
) -> AudioValidationResult:
    if not file_name.lower().endswith(".wav"):
        raise SecurityValidationError("Only WAV files are allowed.")

    size_bytes = len(audio_bytes)
    if size_bytes == 0:
        raise SecurityValidationError("The uploaded file is empty.")
    if size_bytes > max_size_bytes:
        raise SecurityValidationError("The uploaded file is too large.")

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
            if frame_rate <= 0:
                raise SecurityValidationError("The uploaded file is not a valid WAV file.")
            duration_seconds = frame_count / frame_rate
    except (wave.Error, EOFError):
        raise SecurityValidationError("The uploaded file is not a valid WAV file.") from None

    if duration_seconds > max_duration_seconds:
        raise SecurityValidationError("The uploaded audio is too long.")

    return AudioValidationResult(duration_seconds=duration_seconds, size_bytes=size_bytes)


def seconds_until_allowed(
    last_processed_at: datetime | None,
    now: datetime,
    cooldown_seconds: int,
) -> int:
    if last_processed_at is None:
        return 0

    elapsed_seconds = (now - last_processed_at).total_seconds()
    remaining_seconds = cooldown_seconds - int(elapsed_seconds)
    return max(0, remaining_seconds)
