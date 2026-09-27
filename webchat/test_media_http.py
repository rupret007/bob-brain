"""Authenticated, isolated HTTP tests for media in/out; no live providers."""
import base64
import http.client
import json
import threading
import unittest
import uuid
from unittest.mock import patch

import chat_media as media
import test_webchat as fixtures
from app import Server
from test_chat_media import png_fixture


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


if __name__ == '__main__':
    unittest.main()
