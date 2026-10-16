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


if __name__ == "__main__":
    unittest.main()
