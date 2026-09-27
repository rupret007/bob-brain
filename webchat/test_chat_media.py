#!/usr/bin/env python3
"""Unit tests for chat media attachments."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_media import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    enrich_for_model,
    public_attachment,
    store_media,
    strip_assistant_attachment_markers,
    validate_attachment_ids,
)


class ChatMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_store_and_validate_image(self):
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        stored = store_media(self.root, png, "dot.png")
        self.assertEqual(stored["kind"], "image")
        metas = validate_attachment_ids(self.root, [stored["media_id"]])
        self.assertEqual(len(metas), 1)
        bundle = enrich_for_model(self.root, metas)
        self.assertIn("Image attachment", bundle["text"])
        self.assertEqual(len(bundle["vision"]), 1)

    def test_reject_too_many_attachments(self):
        ids = ["abcdabcdabcdabcd"] * (MAX_ATTACHMENTS_PER_MESSAGE + 1)
        with self.assertRaises(ValueError):
            validate_attachment_ids(self.root, ids)

    def test_strip_assistant_markers(self):
        content = 'Here you go <bob-webchat-attachment media_id="abcdabcdabcdabcd" label="chart" />.'
        cleaned, items = strip_assistant_attachment_markers(content)
        self.assertNotIn("bob-webchat-attachment", cleaned)
        self.assertEqual(items[0]["media_id"], "abcdabcdabcdabcd")

    def test_public_attachment_shape(self):
        meta = {"media_id": "abcdabcdabcdabcd", "filename": "x.png", "kind": "image", "bytes": 3}
        pub = public_attachment(meta)
        self.assertEqual(pub["url"], "/api/media/abcdabcdabcdabcd")

    @patch("chat_media.extract_video_frames", return_value=[{"time_s": 0, "mime": "image/jpeg", "data_base64": "YQ=="}])
    @patch("chat_media.extract_audio_transcript", return_value="hello from video")
    @patch("chat_media._probe_duration", return_value=5.0)
    def test_video_enrich_uses_frames_and_transcript(self, *_mocks):
        stored = store_media(self.root, b"\x00\x00\x00\x18ftypmp42", "clip.mp4")
        bundle = enrich_for_model(self.root, [stored])
        self.assertIn("Video attachment", bundle["text"])
        self.assertIn("hello from video", bundle["text"])
        self.assertGreaterEqual(len(bundle["vision"]), 1)


if __name__ == "__main__":
    unittest.main()
