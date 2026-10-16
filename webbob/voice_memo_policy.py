"""Voice memos never land in shared memory as audio or transcripts."""
import re
import unicodedata

from webbob.shared_context import ContextError, safe_fact

_MEMO_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

RECALL_FIELDS = frozenset({"memo_id", "recorded_at", "duration_seconds", "transcription_status"})
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {"audio", "audio_base64", "transcript", "transcription", "voice", "wav", "mp3", "m4a", "ogg"}
)


class VoiceMemoPolicyError(ValueError):
    pass


def _normalize_payload_key(key):
    """NFKC + casefold; strip Cf/invisible chars and whitespace; map long s to s.

    Forbidden stems (FORBIDDEN_PAYLOAD_KEYS) are matched as substrings of the result.
    """
    if not isinstance(key, str):
        key = str(key)
    normalized = unicodedata.normalize("NFKC", key).replace("\u017f", "s")
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")
    normalized = "".join(ch for ch in normalized if not ch.isspace())
    return normalized.casefold()


def _payload_key_forbidden(key):
    norm = _normalize_payload_key(key)
    return any(stem in norm for stem in FORBIDDEN_PAYLOAD_KEYS)


def validate_recall_metadata(record):
    if not isinstance(record, dict) or set(record) != RECALL_FIELDS:
        raise VoiceMemoPolicyError("voice recall may store metadata only")
    if record["transcription_status"] not in ("unavailable", "on_device_only", "not_requested"):
        raise VoiceMemoPolicyError("shared memory cannot hold transcription text")
    if not isinstance(record["memo_id"], str) or not _MEMO_ID.fullmatch(record["memo_id"]):
        raise VoiceMemoPolicyError("invalid memo id")
    if type(record["duration_seconds"]) is not int or not 0 <= record["duration_seconds"] <= 86_400:
        raise VoiceMemoPolicyError("invalid duration")
    if type(record["recorded_at"]) not in (int, float):
        raise VoiceMemoPolicyError("invalid timestamp")
    return record


def reject_voice_content(value):
    if isinstance(value, dict):
        for key in value:
            if _payload_key_forbidden(key):
                raise VoiceMemoPolicyError("voice payload keys forbidden in shared memory")
        for nested in value.values():
            reject_voice_content(nested)
        return
    if not isinstance(value, str):
        raise VoiceMemoPolicyError("voice content must be explicit text to validate")
    try:
        safe_fact(value)
    except ContextError:
        raise VoiceMemoPolicyError("voice or transcript content forbidden in shared memory") from None
