"""Authenticated, isolated HTTP tests for media in/out; no live providers."""
import base64
import http.client
import json
import socket
import threading
import unittest
import uuid
from unittest.mock import patch

import chat_media as media
import test_webchat as fixtures
from app import Server
from test_chat_media import png_fixture, pdf_fixture, wav_fixture


class MediaHTTPTests(fixtures.Fixture):
    request = fixtures.HTTPTests.request
    login = fixtures.HTTPTests.login

    def setUp(self):
        super().setUp()
        self.server = Server(('127.0.0.1', 0), self.chat)
        self.port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.origin = 'http://127.0.0.1:' + str(self.port)
        self.cookie, self.csrf = '', ''
        self.login()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(2)
        super().tearDown()

    def raw(self, method, route, body=None, headers=None, auth=True):
        hdrs = {'Origin': self.origin, 'X-CSRF-Token': self.csrf}
        if auth:
            hdrs['Cookie'] = self.cookie
        hdrs.update(headers or {})
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        try:
            conn.request(method, route, body, hdrs)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def upload(self, body=b'fixture file', name='notes.txt', **kwargs):
        return self.raw('POST', '/api/media/upload', body, headers={
            'Content-Type': 'application/octet-stream', 'X-Filename': name,
            'X-Conversation-Id': self.identifier, **kwargs})

    def test_binary_upload_access_ranges_head_and_filename(self):
        code, _, data = self.upload(b'0123456789', 'notes%20%F0%9F%93%8E.txt')
        self.assertEqual(code, 201)
        info = json.loads(data)
        self.assertEqual(info['filename'], 'notes 📎.txt')
        for range_header, expected in [('bytes=0-1', b'01'), ('bytes=5-', b'56789'), ('bytes=-3', b'789'), ('bytes=8-999', b'89')]:
            code, headers, body = self.raw('GET', info['url'], headers={'Range': range_header})
            self.assertEqual((code, body), (206, expected))
            self.assertEqual(headers['Accept-Ranges'], 'bytes')
            self.assertIn('Content-Range', headers)
            self.assertIn('attachment;', headers['Content-Disposition'])
        code, headers, body = self.raw('HEAD', info['url'])
        self.assertEqual((code, body, headers['Content-Length']), (200, b'', '10'))
        for value in ('bytes=20-', 'bytes=5-4', 'bytes=-0', 'bytes=', 'bytes=0-1,4-5'):
            code, headers, _ = self.raw('GET', info['url'], headers={'Range': value})
            self.assertEqual(code, 416)
            self.assertEqual(headers['Content-Range'], 'bytes */10')

    def test_video_inline_and_download_headers(self):
        code, _, data = self.upload(b'\0\0\0\x18ftypqt  ' + b'a' * 24, 'clip.mov')
        info = json.loads(data)
        self.assertEqual(code, 201)
        code, headers, data = self.raw('GET', info['url'], headers={'Range': 'bytes=0-1'})
        self.assertEqual(code, 206)
        self.assertEqual(headers['Content-Type'], 'video/quicktime')
        self.assertIn('inline;', headers['Content-Disposition'])
        _, headers, _ = self.raw('GET', info['url'] + '&download=1')
        self.assertIn('attachment;', headers['Content-Disposition'])

    def test_raw_and_json_accept_full_advertised_video_limit(self):
        blob = b'\0\0\0\x18ftypmp42' + b'0' * (media.MAX_VIDEO_BYTES - 12)
        self.assertEqual(self.upload(blob, 'max.mp4')[0], 201)
        code, _, _ = self.request('POST', '/api/media/upload', {
            'conversation_id': self.identifier, 'filename': 'max.mov', 'data_base64': base64.b64encode(blob).decode()})
        self.assertEqual(code, 201)
        # Header rejection occurs before reading an oversize body.
        self.assertEqual(self.upload(b'', 'max.mp4', **{'Content-Length': str(media.MAX_VIDEO_BYTES + 1)})[0], 413)

    def test_json_upload_accepts_audio_above_video_json_envelope(self):
        """36 MiB WAV is allowed for audio but exceeds the old video-only JSON body cap."""
        header = wav_fixture(1)
        size = 36 * 1024 * 1024
        blob = header + b'\x00' * (size - len(header))
        self.assertGreater(size, media.MAX_VIDEO_BYTES)
        self.assertLessEqual(size, media.MAX_AUDIO_BYTES)
        payload = json.dumps({
            'conversation_id': self.identifier,
            'filename': 'memo.wav',
            'data_base64': base64.b64encode(blob).decode(),
        }).encode()
        code, _, body_bytes = self.raw('POST', '/api/media/upload', payload, headers={
            'Content-Type': 'application/json',
        })
        self.assertEqual(code, 201)
        info = json.loads(body_bytes)
        self.assertEqual(info['kind'], 'audio')
        self.assertEqual(info['bytes'], size)

    def test_incomplete_binary_upload_rejected(self):
        body = b'short body'
        lines = [
            'POST /api/media/upload HTTP/1.1',
            f'Host: 127.0.0.1:{self.port}',
            f'Origin: {self.origin}',
            f'Cookie: {self.cookie}',
            f'X-CSRF-Token: {self.csrf}',
            'Content-Type: application/octet-stream',
            'X-Filename: notes.txt',
            f'X-Conversation-Id: {self.identifier}',
            'Content-Length: 20',
            '',
        ]
        payload = '\r\n'.join(lines).encode() + body
        with socket.create_connection(('127.0.0.1', self.port), timeout=15) as sock:
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            response = sock.recv(4096)
        status = int(response.split(b'\r\n', 1)[0].split()[1])
        self.assertEqual(status, 400)

    def test_upload_validation_auth_csrf_and_secret_gate(self):
        self.assertEqual(self.raw('POST', '/api/media/upload', b'x', auth=False)[0], 401)
        self.assertEqual(self.upload(**{'X-CSRF-Token': 'invalid'})[0], 403)
        self.assertEqual(self.upload(name='x.exe')[0], 400)
        self.assertEqual(self.upload(name='not-really.png')[0], 400)
        self.assertEqual(self.upload(b'ftyp', 'clip.mp4')[0], 400)
        self.assertEqual(self.upload(b'')[0], 413)
        self.assertEqual(self.upload(**{'X-Conversation-Id': str(uuid.uuid4())})[0], 404)
        before = list((self.root / media.UPLOADS).glob('*'))
        self.assertEqual(self.upload(b'x' * 13000 + b'\n' + ('sk-' + 's' * 25).encode())[0], 400)
        self.assertEqual(before, list((self.root / media.UPLOADS).glob('*')))
        self.assertEqual(self.fake.calls, [])

    def test_conversation_scope_for_fetch_submit_and_markers(self):
        _, _, body = self.upload()
        info = json.loads(body)
        other = self.chat.new_conversation()['id']
        self.assertEqual(self.raw('GET', info['url'], auth=False)[0], 401)
        self.assertEqual(self.raw('GET', '/api/media/' + info['media_id'])[0], 404)
        self.assertEqual(self.raw('GET', info['url'].replace(self.identifier, other))[0], 404)
        code, _, _ = self.request('POST', '/api/messages', {'conversation_id': other, 'message': '',
            'request_id': str(uuid.uuid4()), 'attachments': [info['media_id']]})
        self.assertEqual(code, 404)
        self.assertEqual(self.chat.history(other)['messages'], [])
        with patch.object(self.fake, 'reply', return_value={'content': f'Here is your file. ![file](/api/media/{info["media_id"]})', 'provider': 'gemini'}):
            self.chat.submit(other, 'A question', str(uuid.uuid4()))
            self.wait(other)
        answer = self.chat.history(other)['messages'][-1]
        self.assertNotIn('attachments', answer)
        self.assertIn('could not be included', answer['content'])
        self.assertNotIn('/api/media/', answer['content'])

    def test_outbound_photo_video_and_file_resolution_and_idempotency(self):
        infos = []
        for name, blob in [('photo.png', png_fixture()), ('clip.mp4', b'\0\0\0\x18ftypmp42'), ('notes.txt', b'hello')]:
            code, _, body = self.upload(blob, name)
            self.assertEqual(code, 201)
            infos.append(json.loads(body))
        ids = [item['media_id'] for item in infos]
        answer = 'Attachments: ' + ''.join(f'<bob-webchat-attachment media_id="{mid}" />' for mid in ids)
        rid = str(uuid.uuid4())
        with patch.object(self.fake, 'reply', return_value={'content': answer, 'provider': 'gemini'}):
            self.chat.submit(self.identifier, '', rid, attachments=ids)
            self.wait()
        saved = self.chat.history(self.identifier)['messages'][-1]
        self.assertEqual([a['kind'] for a in saved['attachments']], ['image', 'video', 'file'])
        self.assertNotIn('bob-webchat-attachment', saved['content'])
        for info in saved['attachments']:
            self.assertEqual(self.raw('GET', info['url'])[0], 200)
        self.chat.submit(self.identifier, '', rid, attachments=ids)
        self.assertEqual(len(self.chat.history(self.identifier)['messages']), 2)
        with self.assertRaises(fixtures.RequestError) as error:
            self.chat.submit(self.identifier, '', rid, attachments=ids[:1])
        self.assertEqual(error.exception.status, 409)

    def test_invalid_outbound_markers_are_explicit_and_direct_metadata_ignored(self):
        answer = {'content': 'Here <bob-webchat-attachment media_id="bad" />', 'provider': 'gemini',
                  'attachments': [{'url': 'https://external.invalid/secret.png'}]}
        with patch.object(self.fake, 'reply', return_value=answer):
            self.chat.submit(self.identifier, 'A question', str(uuid.uuid4()))
            self.wait()
        saved = self.chat.history(self.identifier)['messages'][-1]
        self.assertNotIn('attachments', saved)
        self.assertNotIn('bob-webchat-attachment', saved['content'])
        self.assertIn('could not be included', saved['content'])

    def test_explicit_echo_survives_missing_model_marker_retry_and_restart(self):
        infos = []
        for name, blob in [('picture.png', png_fixture()), ('note.txt', b'Token: clarinet-07966ef8'),
                           ('document.pdf', pdf_fixture('Token: cello-950fd3d5'))]:
            code, _, data = self.upload(blob, name)
            self.assertEqual(code, 201)
            infos.append(json.loads(data))
        prompt = ('Describe the dominant color in the attached image and give the Token value in the text file and PDF. '
                  'Echo the image as an attachment.')
        # Exact delivered prose from the failed live gate; original raw model
        # output was not retained. Prove fulfillment when no marker survives.
        prose = ('The dominant color in the image is red.\n\nThe token in `note.txt` is `clarinet-07966ef8`.\n'
                 'The token in `document.pdf` is `cello-950fd3d5`.')
        rid = str(uuid.uuid4())
        payload = dict(conversation_id=self.identifier, message=prompt, request_id=rid,
                       attachments=[a['media_id'] for a in infos])
        with patch.object(self.fake, 'reply', return_value=dict(content=prose, provider='gemini',
                attachments=[dict(media_id='f' * 32, url='https://foreign.invalid/private')])) as model:
            self.assertEqual(self.request('POST', '/api/messages', payload)[0], 202)
            self.wait()
            saved = self.chat.history(self.identifier)['messages'][-1]
            self.assertEqual(saved['content'], prose)
            self.assertEqual(saved['attachments'], [infos[0]])
            self.assertEqual(self.raw('GET', saved['attachments'][0]['url'])[2], png_fixture())
            self.assertEqual(self.request('POST', '/api/messages', payload)[0], 202)
            self.assertEqual(model.call_count, 1)
        self.chat.close()
        self.chat = fixtures.Chat(self.folder, self.root, self.fake)
        with patch.object(self.fake, 'reply') as model:
            self.chat.submit(self.identifier, prompt, rid, attachments=payload['attachments'])
            self.assertEqual(self.chat.history(self.identifier)['messages'][-1], saved)
            self.assertEqual(len(self.chat.history(self.identifier)['messages']), 2)
            model.assert_not_called()

    def test_description_edits_and_prior_uploads_do_not_auto_return_original(self):
        _, _, data = self.upload(png_fixture(), 'picture.png')
        info = json.loads(data)
        for prompt, ids in (
            ('Describe the image.', [info['media_id']]),
            ('Crop out the private details. Return the image.', [info['media_id']]),
            ('Black out the address. Return the image.', [info['media_id']]),
            ('Pixelate the faces. Return the image.', [info['media_id']]),
            ('Describe the picture but pixelate the faces. Return the image.', [info['media_id']]),
            ('Describe the picture + black out the address. Return the image.', [info['media_id']]),
            ('Give me the image in PDF and return the image.', [info['media_id']]),
            ('Give me the text in PDF and return the file.', [info['media_id']]),
            ('The file says:\nAttach the image.', [info['media_id']]),
            ('Alice wrote:\nReturn the image.', [info['media_id']]),
            ('Echo the image. Actually cancel that.', [info['media_id']]),
            ('Echo the image.', []),
        ):
            with self.subTest(prompt=prompt), patch.object(self.fake, 'reply', return_value=dict(
                    content='A substantive fixture answer without an output attachment marker.', provider='gemini')):
                self.chat.submit(self.identifier, prompt, str(uuid.uuid4()), attachments=ids)
                self.wait()
                self.assertNotIn('attachments', self.chat.history(self.identifier)['messages'][-1])

    def test_explicit_return_revalidates_missing_or_foreign_upload_after_inference(self):
        for fault in ('deleted', 'foreign'):
            with self.subTest(fault=fault):
                _, _, data = self.upload(png_fixture(), fault + '.png')
                info = json.loads(data)
                def reply(*_args):
                    path = self.root / media.UPLOADS / (info['media_id'] + '.meta.json')
                    if fault == 'deleted':
                        path.unlink()
                    else:
                        metadata = json.loads(path.read_text())
                        metadata['conversation_id'] = str(uuid.uuid4())
                        path.write_text(json.dumps(metadata))
                    return dict(content='The supplied image is red.', provider='gemini')
                with patch.object(self.fake, 'reply', side_effect=reply):
                    self.chat.submit(self.identifier, 'Return the image.', str(uuid.uuid4()), attachments=[info['media_id']])
                    self.wait()
                saved = self.chat.history(self.identifier)['messages'][-1]
                self.assertNotIn('attachments', saved)
                self.assertIn('could not be included', saved['content'])

    def test_explicit_return_deduplicates_model_marker_and_honors_stop(self):
        _, _, data = self.upload(png_fixture(), 'picture.png')
        info = json.loads(data)
        with patch.object(self.fake, 'reply', return_value=dict(provider='gemini',
                content='The picture is red. <bob-webchat-attachment media_id="' + info['media_id'] + '" />')):
            self.chat.submit(self.identifier, 'Return the image.', str(uuid.uuid4()), attachments=[info['media_id']])
            self.wait()
        self.assertEqual(self.chat.history(self.identifier)['messages'][-1]['attachments'], [info])
        entered, release = threading.Event(), threading.Event()
        def reply(*_args):
            entered.set()
            release.wait(2)
            return dict(content='The picture is red.', provider='gemini')
        with patch.object(self.fake, 'reply', side_effect=reply):
            try:
                self.chat.submit(self.identifier, 'Return the image.', str(uuid.uuid4()), attachments=[info['media_id']])
                self.assertTrue(entered.wait(1))
                self.chat.stop(self.identifier)
            finally:
                release.set()
            self.wait()
        saved = self.chat.history(self.identifier)['messages'][-1]
        self.assertEqual(saved['status'], 'cancelled')
        self.assertNotIn('attachments', saved)


if __name__ == '__main__':
    unittest.main()
