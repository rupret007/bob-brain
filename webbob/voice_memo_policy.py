"""Voice memos never land in shared memory as audio or transcripts."""
from webbob.shared_context import ContextError, safe_fact

RECALL_FIELDS = frozenset({"memo_id", "recorded_at", "duration_seconds", "transcription_status"})
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {"audio", "audio_base64", "transcript", "transcription", "voice", "wav", "mp3", "m4a", "ogg"}
)


class VoiceMemoPolicyError(ValueError):
    pass


def validate_recall_metadata(record):
    if not isinstance(record, dict) or set(record) != RECALL_FIELDS:
        raise VoiceMemoPolicyError("voice recall may store metadata only")
    if record["transcription_status"] not in ("unavailable", "on_device_only", "not_requested"):
        raise VoiceMemoPolicyError("shared memory cannot hold transcription text")
    if not isinstance(record["memo_id"], str) or not 1 <= len(record["memo_id"]) <= 80:
        raise VoiceMemoPolicyError("invalid memo id")
    if type(record["duration_seconds"]) is not int or not 0 <= record["duration_seconds"] <= 86_400:
        raise VoiceMemoPolicyError("invalid duration")
    if type(record["recorded_at"]) not in (int, float):
        raise VoiceMemoPolicyError("invalid timestamp")
    return record


def reject_voice_content(value):
    if isinstance(value, dict):
        if FORBIDDEN_PAYLOAD_KEYS.intersection(value):
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
