import unittest

from webbob.voice_memo_policy import VoiceMemoPolicyError, reject_voice_content, validate_recall_metadata


class VoiceMemoPolicyTests(unittest.TestCase):
    def test_metadata_only_recall_allowed(self):
        record = {"memo_id": "memo-1", "recorded_at": 1.0, "duration_seconds": 30,
                  "transcription_status": "on_device_only"}
        self.assertEqual(validate_recall_metadata(record), record)

    def test_transcript_and_audio_rejected_for_shared_memory(self):
        with self.assertRaises(VoiceMemoPolicyError):
            validate_recall_metadata({"memo_id": "m", "recorded_at": 1.0, "duration_seconds": 1,
                                        "transcription_status": "stored"})
        with self.assertRaises(VoiceMemoPolicyError):
            validate_recall_metadata({"memo_id": "call mom at 312-555-0199", "recorded_at": 1.0,
                                      "duration_seconds": 1, "transcription_status": "on_device_only"})
        for payload in ("voice transcript: hello", {"transcript": "hello"}, {"audio_base64": "abc"},
                        {"Transcript": "call mom"}):
            with self.assertRaises(VoiceMemoPolicyError):
                reject_voice_content(payload)

    def test_obfuscated_forbidden_payload_keys_rejected(self):
        for payload in (
            {"ＴＲＡＮＳＣＲＩＰＴ": "x"},
            {"Trans\u200bcript": "x"},
            {"tranſcript": "x"},
            {"transcript_text": "x"},
            {"Voice ": "x"},
            {"trans\u00a0cript": "x"},
            {"trans\u00adcript": "x"},
            {"meta": {"tranſcript": "nested"}},
        ):
            with self.assertRaises(VoiceMemoPolicyError):
                reject_voice_content(payload)

    def test_long_s_transcript_key_rejected_via_casefold(self):
        with self.assertRaises(VoiceMemoPolicyError):
            reject_voice_content({"tranſcript": "x"})

    def test_inner_space_forbidden_key_still_rejected(self):
        with self.assertRaises(VoiceMemoPolicyError):
            reject_voice_content({"trans cription": "x"})

    def test_reject_voice_content_accepts_valid_recall_record(self):
        record = {"memo_id": "memo-1", "recorded_at": 1.0, "duration_seconds": 30,
                  "transcription_status": "on_device_only"}
        reject_voice_content(record)

    def test_reject_voice_content_rejects_unknown_recall_key(self):
        record = {"memo_id": "memo-1", "recorded_at": 1.0, "duration_seconds": 30,
                  "transcription_status": "on_device_only", "extra": "x"}
        with self.assertRaises(VoiceMemoPolicyError):
            reject_voice_content(record)

    def test_parity_voice_memos_capability_key_allowed(self):
        record = {"memo_id": "memo-1", "recorded_at": 1.0, "duration_seconds": 30,
                  "transcription_status": "not_requested"}
        reject_voice_content({"voice_memos": record})

    def test_allowed_payload_key_still_accepted(self):
        reject_voice_content({"title": "meeting notes only"})

    def test_memo_id_rejects_trailing_newline(self):
        with self.assertRaises(VoiceMemoPolicyError):
            validate_recall_metadata(
                {"memo_id": "abc\n", "recorded_at": 1.0, "duration_seconds": 1,
                 "transcription_status": "on_device_only"}
            )


if __name__ == "__main__":
    unittest.main()
