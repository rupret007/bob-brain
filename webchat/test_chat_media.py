#!/usr/bin/env python3
"""Offline media regressions. All provider and decoder failures are controlled."""
import base64
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
import zlib
from pathlib import Path
from unittest.mock import patch

import chat_media as media
from providers import Cancelled, ProviderError, Redactor


def png_fixture():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\0\0' * 8) * 8)) + chunk(b'IEND', b''))


def pdf_fixture(text='Offline PDF text'):
    stream = ('BT /F1 14 Tf 30 100 Td (' + text + ') Tj ET').encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1000 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    data, offsets = b'%PDF-1.4\n', [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(index).encode() + b' 0 obj\n' + body + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return data + f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


class ChatMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cid = str(uuid.uuid4())
        self.redact = Redactor(self.root, 'offline-password-fixture')

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, data=b'hello', name='notes.txt'):
        return media.store_media(self.root, data, name, conversation_id=self.cid, redact=self.redact)

    def enrich(self, metas, **kwargs):
        return media.enrich_for_model(self.root, metas, redact=self.redact, **kwargs)

    def test_store_validate_and_private_permissions(self):
        stored = self.store(png_fixture(), 'dot.PNG')
        self.assertEqual(stored['kind'], 'image')
        loaded = media.validate_attachment_ids(self.root, [stored['media_id']] * 2, conversation_id=self.cid)
        self.assertEqual(len(loaded), 1)
        self.assertEqual((self.root / stored['path']).stat().st_mode & 0o777, 0o600)
        sidecar = self.root / media.UPLOADS / (stored['media_id'] + '.meta.json')
        self.assertEqual(sidecar.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / media.UPLOADS).stat().st_mode & 0o777, 0o700)
        self.assertIn('conversation_id=' + self.cid, media.public_attachment(stored)['url'])

    def test_owner_metadata_required_no_glob_fallback(self):
        stored = self.store()
        mid = stored['media_id']
        for cid in (str(uuid.uuid4()), '', None):
            with self.assertRaises(FileNotFoundError):
                media.load_meta(self.root, mid, conversation_id=cid)
        sidecar = self.root / media.UPLOADS / (mid + '.meta.json')
        for invalid in ('{}', '[]', '{', json.dumps({**stored, 'suffix': '/../notes.txt'})):
            sidecar.write_text(invalid)
            with self.assertRaises(FileNotFoundError):
                media.resolve_media(self.root, mid, conversation_id=self.cid)
        sidecar.unlink()
        with self.assertRaises(FileNotFoundError):
            media.load_meta(self.root, mid, conversation_id=self.cid)

    def test_symlink_blobs_cannot_escape_store(self):
        stored = self.store()
        blob = self.root / stored['path']
        outside = self.root / 'outside.txt'
        outside.write_text('private')
        blob.unlink()
        blob.symlink_to(outside)
        with self.assertRaises(FileNotFoundError):
            media.load_meta(self.root, stored['media_id'], conversation_id=self.cid)

    def test_invalid_inputs_and_size_boundaries(self):
        for name, data in [('archive.zip', b'x'), ('x.txt', b''), ('bad.png', b'html'), ('clip.mov', b'#EXTM3U\n'),
                           ('clip.mp4', b'ftyp'), ('x.txt', b'\x00'), ('bad\n.txt', b'x')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store(data, name)
        for name, size, prefix in [('photo.png', media.MAX_IMAGE_BYTES, png_fixture()),
                                    ('clip.mov', media.MAX_VIDEO_BYTES, b'\x00\x00\x00\x18ftypqt  '),
                                    ('notes.txt', media.MAX_FILE_BYTES, b'hello')]:
            data = prefix + b'a' * (size - len(prefix))
            stored = self.store(data, name)
            self.assertEqual(stored['bytes'], size)
            with self.assertRaisesRegex(ValueError, 'too large'):
                self.store(data + b'a', name)
        for ids in ('', {}, ['bad'], ['a' * 16] * 7, ['a' * 32] * 7):
            with self.assertRaises(ValueError):
                media.validate_attachment_ids(self.root, ids, conversation_id=self.cid)

    def test_store_rejects_mismatched_signature(self):
        png_data = b'\x89PNG\r\n\x1a\n' + b'fake png content'
        with self.assertRaises(ValueError) as ctx:
            media.store_media(self.root, png_data, 'fake.jpg', conversation_id=self.cid, redact=self.redact)
        self.assertIn('does not match', str(ctx.exception))

    def test_whitespace_filename_rejected(self):
        with self.assertRaises(ValueError):
            media.media_limit('   ')

    def test_secret_uploads_rejected_before_persistence(self):
        secret = 'sk-' + 'a' * 25
        for body, name in [(b'a' * 13000 + b'\n' + secret.encode(), 'secrets.txt'), (b'hello', secret + '.txt')]:
            with self.assertRaisesRegex(ValueError, 'secret'):
                self.store(body, name)
        self.assertFalse(list((self.root / media.UPLOADS).glob('*')))

    def test_file_and_transcript_redacted_before_model(self):
        secret = 'sk-' + 'b' * 25
        stored = self.store(b'placeholder', 'legacy.txt')
        (self.root / stored['path']).write_bytes(secret.encode())
        stored = media.load_meta(self.root, stored['media_id'], conversation_id=self.cid)
        bundle = self.enrich([stored])
        self.assertNotIn(secret, json.dumps(bundle))
        self.assertIn('[secret removed]', bundle['text'])
        video = self.store(b'\0\0\0\x18ftypmp42', 'clip.mp4')
        frames = [{'time_s': 0, 'mime': 'image/jpeg', 'data_base64': 'YQ=='}]
        with patch.object(media, '_probe_duration', return_value=1), patch.object(media, 'extract_video_frames', return_value=frames), patch.object(media, 'scan_image', return_value=''), patch.object(media, 'extract_audio_transcript', return_value=secret):
            bundle = self.enrich([video])
        self.assertNotIn(secret, json.dumps(bundle))
        self.assertEqual(len(bundle['vision']), 1)

    def test_ocr_secret_and_failure_withhold_visual_payload(self):
        image = self.store(png_fixture(), 'photo.png')
        for error in ('Image analysis blocked: visible text appears to contain a secret.', 'Local safety check unavailable.'):
            with patch.object(media, 'prompt_image_bytes', return_value=(b'jpeg', 'jpeg')), patch.object(media, 'scan_image', side_effect=ValueError(error)):
                bundle = self.enrich([image])
            self.assertEqual(bundle['vision'], [])
            self.assertIn(error, bundle['warnings'][0])
        with patch.object(media.shutil, 'which', return_value='/fake/tesseract'), patch.object(media.MediaBudget, 'run', return_value='sk-' + 'c' * 25):
            with self.assertRaisesRegex(ValueError, 'secret'):
                media.scan_image(b'jpeg', media.MediaBudget(), self.redact)
        with patch.object(media.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'not installed'):
                media.scan_image(b'jpeg', media.MediaBudget(), self.redact)

    def test_video_secret_frame_drops_entire_clip(self):
        video = self.store(b'\0\0\0\x18ftypmp42', 'clip.mp4')
        frames = [{'time_s': n, 'mime': 'image/jpeg', 'data_base64': 'YQ=='} for n in (0, 1)]
        with patch.object(media, '_probe_duration', return_value=1), patch.object(media, 'extract_video_frames', return_value=frames), patch.object(media, 'scan_image', side_effect=['safe', ValueError('secret detected')]):
            bundle = self.enrich([video])
        self.assertEqual(bundle['vision'], [])
        self.assertIn('secret detected', bundle['warnings'][0])

    def test_partial_failure_keeps_other_file_and_explains_video_failure(self):
        video = self.store(b'\0\0\0\x18ftypmp42', 'broken.mov')
        text = self.store(b'keep this context')
        with patch.object(media, '_probe_duration', return_value=None), patch.object(media, '_run_ffmpeg', side_effect=ValueError('decoder timeout')):
            bundle = self.enrich([video, text])
        self.assertIn('keep this context', bundle['text'])
        self.assertIn('No video frames', bundle['warnings'][0])

    def test_prompt_image_progressive_fallback(self):
        huge = b'x' * (media.MAX_PROMPT_IMAGE_BYTES + 1)
        ok = b'\xff\xd8\xff' + b'y' * 100
        with patch.object(media, '_run_ffmpeg') as ffmpeg:
            def write_jpeg(args, budget=None):
                out = Path(args[-1])
                out.write_bytes(huge if 'image_q6' in str(out) else ok)
            ffmpeg.side_effect = write_jpeg
            blob, fmt = media.prompt_image_bytes(Path('photo.png'))
        self.assertEqual((blob, fmt), (ok, 'jpeg'))
        self.assertGreaterEqual(ffmpeg.call_count, 2)

    def test_read_text_file_non_pdf_round_trip(self):
        path = self.root / 'plain.txt'
        path.write_text('plain text excerpt', encoding='utf-8')
        self.assertEqual(media.read_text_file(path), 'plain text excerpt')

    def test_timeout_missing_tools_and_probe_nonfinite(self):
        budget = media.MediaBudget()
        with patch('providers.run', side_effect=ProviderError(kind='timeout')):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                budget.run(['decoder'])
        for value in ('nan', 'inf', '-1', 'N/A'):
            with patch.object(media.shutil, 'which', return_value='ffprobe'), patch.object(media.MediaBudget, 'run', return_value=value):
                self.assertIsNone(media._probe_duration(Path('fixture.mp4')))
        with patch.object(media.shutil, 'which', return_value=None):
            self.assertIsNone(media._probe_duration(Path('fixture.mp4')))
            self.assertEqual(media.extract_audio_transcript(Path('fixture.mp4')), '')
            with self.assertRaisesRegex(ValueError, 'ffmpeg'):
                media.prompt_image_bytes(Path('fixture.heic'))

    def test_shared_deadline_and_cancellation(self):
        budget = media.MediaBudget(seconds=.1)
        with patch('providers.run', return_value=(0, '', '')) as run:
            budget.run(['decoder'], timeout=120)
            self.assertLessEqual(run.call_args.kwargs['timeout'], .1)
        with self.assertRaisesRegex(ValueError, 'timed out'):
            media.MediaBudget(seconds=-1).run(['decoder'])
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            media.MediaBudget(cancel).run(['decoder'])

    def test_cancel_terminates_actual_media_child(self):
        cancel = threading.Event()
        timer = threading.Timer(.2, cancel.set)
        timer.start()
        before = time.monotonic()
        try:
            with self.assertRaises(Cancelled):
                media.MediaBudget(cancel).run([sys.executable, '-c', 'import time; time.sleep(60)'])
            self.assertLess(time.monotonic() - before, 3)
        finally:
            timer.cancel()

    def test_concurrency_bound_fails_visibly(self):
        media.PROCESS_SLOTS.acquire()
        media.PROCESS_SLOTS.acquire()
        try:
            bundle = self.enrich([self.store()])
            self.assertIn('busy', bundle['warnings'][0])
        finally:
            media.PROCESS_SLOTS.release()
            media.PROCESS_SLOTS.release()

    def test_pdf_without_reader_is_explicit(self):
        pdf = self.store(b'%PDF-1.4\nfixture', 'notes.pdf')
        with patch.object(media.shutil, 'which', return_value=None):
            bundle = self.enrich([pdf])
        self.assertIn('PDF text extraction is unavailable', bundle['warnings'][0])
        self.assertNotIn('%PDF', bundle['text'])

    def test_store_requires_redact_callable(self):
        with self.assertRaisesRegex(ValueError, 'redact'):
            media.store_media(self.root, b'hello', 'notes.txt', conversation_id=self.cid, redact=None)

    def test_marker_stripping_including_invalid_markdown(self):
        text = ('Here <bob-webchat-attachment media_id="bad" /> '
                '![photo](/api/media/abcdabcdabcdabcd) [file](/api/media/0123456789abcdef?conversation_id=test) '
                '<bob-webchat-attachment nope>')
        cleaned, items = media.strip_assistant_attachment_markers(text)
        self.assertEqual(cleaned, 'Here')
        self.assertEqual([x['media_id'] for x in items], ['bad', '', 'abcdabcdabcdabcd', '0123456789abcdef'])
        upper, upper_items = media.strip_assistant_attachment_markers(
            'See ![x](/API/MEDIA/0123456789ABCDEF0123456789ABCDEF)')
        self.assertEqual(upper, 'See')
        self.assertEqual(upper_items[0]['media_id'], '0123456789ABCDEF0123456789ABCDEF')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('tesseract'), 'local media tools unavailable')
    def test_real_png_normalization_and_local_ocr(self):
        bundle = self.enrich([self.store(png_fixture(), 'red.png')])
        self.assertEqual(bundle['warnings'], [])
        self.assertEqual(bundle['vision'][0]['mime'], 'image/jpeg')
        self.assertTrue(base64.b64decode(bundle['vision'][0]['data_base64']).startswith(b'\xff\xd8'))


    def test_whisper_timeout_and_missing_audio_are_safe(self):
        with patch.object(media.shutil, 'which', return_value='whisper'), patch.object(Path, 'is_file', return_value=True), patch.object(media, '_run_ffmpeg'), patch.object(media.MediaBudget, 'run', side_effect=ValueError('timeout')):
            self.assertEqual(media.extract_audio_transcript(Path('fixture.mov')), '')
        with patch.object(media.shutil, 'which', return_value='whisper'), patch.object(Path, 'is_file', return_value=True), patch.object(media, '_run_ffmpeg', side_effect=ValueError('no audio')):
            self.assertEqual(media.extract_audio_transcript(Path('fixture.mov')), '')

    @unittest.skipUnless(shutil.which('pdftotext') or (sys.platform == 'darwin' and shutil.which('osascript')), 'PDF reader unavailable')
    def test_real_pdf_extraction_and_redaction(self):
        secret = 'sk-' + 'p' * 25
        stored = self.store(pdf_fixture('Offline PDF text'), 'notes.pdf')
        (self.root / stored['path']).write_bytes(pdf_fixture('Offline PDF text ' + secret))
        stored = media.load_meta(self.root, stored['media_id'], conversation_id=self.cid)
        bundle = self.enrich([stored])
        self.assertEqual(bundle['warnings'], [])
        self.assertIn('Offline PDF text', bundle['text'])
        self.assertNotIn(secret, bundle['text'])
        self.assertIn('[secret removed]', bundle['text'])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe') and shutil.which('tesseract'), 'local media tools unavailable')
    def test_real_mov_frames_normalize_and_complete_under_budget(self):
        clip = self.root / 'phone.mov'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=1',
                        '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(clip)], check=True, timeout=10)
        before = time.monotonic()
        with patch.object(media, 'extract_audio_transcript', return_value=''):
            bundle = self.enrich([self.store(clip.read_bytes(), 'phone.mov')])
        self.assertEqual(len(bundle['vision']), media.MAX_VIDEO_FRAMES)
        self.assertTrue(all(part['mime'] == 'image/jpeg' for part in bundle['vision']))
        self.assertIn('sampled frames only', bundle['warnings'][0])
        self.assertLess(time.monotonic() - before, media.MEDIA_PREP_SECONDS)


if __name__ == '__main__':
    unittest.main()
