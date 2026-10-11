"""Drive reads: every Google side effect is injected; no live OAuth or models."""
import copy
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import uuid

from app import Chat
from drive_read import (BODY_LIMIT, DOC_MIME, EXCERPT_LIMIT, HELP, NEEDS_AUTH, TEXT_MIME,
                        DriveError, DriveRead, GoogleDrive, parse_target, request)
from local_tasks import LocalFiles, LocalTasks, LocalTaskError
from task_dispatch import task_queue
from texting import Texting
from texting_fixture import OfflineProviders


DOC_ID = '1FixtureGoogleDocId0123456789abcd'
TEXT_ID = '1FixturePlainTextId0123456789efgh'
OTHER_ID = '1OtherConversationFile0123456789'
SECRET_BODIES = (
    '{"client_secret":"fixture-client-secret","refresh_token":"fixture-refresh-secret"}',
    'client_secret,refresh_token\nfixture-client-secret,fixture-refresh-secret',
    '-----BEGIN PRIVATE KEY-----\nfixture-private-key\n-----END PRIVATE KEY-----',
    'Bearer fixture-bearer-token',
    'ya29.fixture-access-token',
    # Even a credential marker beyond the excerpt invalidates the whole read.
    'ordinary prose\n' * EXCERPT_LIMIT + 'refresh_token=fixture-refresh-secret',
)


class FakeDrive:
    def __init__(self):
        self.configured_calls = 0
        self.metadata_calls = []
        self.export_calls = []
        self.download_calls = []
        self.error = None
        self.meta = {
            'id': DOC_ID,
            'name': 'Proposal notes',
            'mimeType': DOC_MIME,
            'modifiedTime': '2026-10-10T18:00:00.000Z',
            'webViewLink': 'https://docs.google.com/document/d/' + DOC_ID + '/edit',
        }
        self.content = 'First paragraph of the doc.'
        self.writes = []

    def configured(self):
        self.configured_calls += 1
        if self.error == NEEDS_AUTH:
            raise DriveError(self.error)

    def metadata(self, file_id):
        self.metadata_calls.append(file_id)
        if self.error:
            raise DriveError(self.error)
        return dict(self.meta, id=file_id)

    def export_text(self, file_id):
        self.export_calls.append(file_id)
        if self.error:
            raise DriveError(self.error)
        return self.content

    def download_text(self, file_id):
        self.download_calls.append(file_id)
        if self.error:
            raise DriveError(self.error)
        return self.content

    def create(self, *args, **kwargs):
        self.writes.append(('create', args, kwargs))
        raise AssertionError('Drive write/create is not part of this feature')

    def share(self, *args, **kwargs):
        self.writes.append(('share', args, kwargs))
        raise AssertionError('Drive share is not part of this feature')

    def update(self, *args, **kwargs):
        self.writes.append(('update', args, kwargs))
        raise AssertionError('Drive update is not part of this feature')


class DriveFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.client = FakeDrive()
        self.actions = DriveRead(self.client)
        self.state = {'holds': {}, 'last_permission': None}
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def say(self, text, cid='chat', request_id=None, state=None):
        return self.actions.handle(text, cid, request_id or str(uuid.uuid4()), state or self.state)

    def assert_failure(self, result):
        self.assertNotIn('Google Drive:', result)
        self.assertNotIn('No text in this file.', result)
        self.assertNotIn('empty', result.lower())
        self.assertNotIn('successfully', result.lower())


class DriveReadTests(DriveFixture):
    def test_google_doc_returns_bounded_excerpt_with_title_time_and_link(self):
        result = self.say('read drive ' + DOC_ID)
        self.assertIn('Google Drive: Proposal notes', result)
        self.assertIn('Modified: 2026-10-10T18:00:00.000Z', result)
        self.assertIn('Source: https://docs.google.com/document/d/' + DOC_ID + '/edit', result)
        self.assertIn('First paragraph of the doc.', result)
        self.assertEqual(self.client.metadata_calls, [DOC_ID])
        self.assertEqual(self.client.export_calls, [DOC_ID])
        self.assertFalse(self.client.download_calls)
        self.assertFalse(self.client.writes)

    def test_plain_text_file_uses_media_download(self):
        self.client.meta.update(id=TEXT_ID, name='notes.txt', mimeType=TEXT_MIME,
                                webViewLink='https://drive.google.com/file/d/' + TEXT_ID + '/view')
        self.client.content = 'plain text body'
        result = self.say('read google drive file ' + TEXT_ID)
        self.assertIn('Google Drive: notes.txt', result)
        self.assertIn('plain text body', result)
        self.assertEqual(self.client.download_calls, [TEXT_ID])
        self.assertFalse(self.client.export_calls)
        self.assertFalse(self.client.writes)

    def test_credential_content_is_rejected_before_receipt_or_excerpt(self):
        for mime in (DOC_MIME, TEXT_MIME):
            for body in SECRET_BODIES:
                with self.subTest(mime=mime, body=body[-80:]):
                    self.client.meta['mimeType'] = mime
                    self.client.content = body
                    result = self.say('read drive ' + DOC_ID)
                    self.assertEqual(result, 'Credential content refused; no Drive file content returned.')
                    self.assert_failure(result)
                    self.assertNotIn('fixture-', result)
                    self.assertFalse(self.client.writes)

    def test_credential_metadata_is_rejected_before_display(self):
        for field, value in (('name', 'client_secret=fixture-client-secret'),
                             ('webViewLink', 'https://drive.google.com/?access_token=fixture-access-token')):
            with self.subTest(field=field):
                original = self.client.meta[field]
                self.client.meta[field] = value
                result = self.say('read drive ' + DOC_ID)
                self.assertIn('Credential content refused', result)
                self.assertNotIn('fixture-', result)
                self.assertNotIn(self.client.content, result)
                self.client.meta[field] = original

    def test_drive_and_docs_urls_are_accepted(self):
        for text in (
                'read google doc https://docs.google.com/document/d/' + DOC_ID + '/edit',
                'read drive https://drive.google.com/file/d/' + DOC_ID + '/view?usp=sharing',
                'Please read the google document https://drive.google.com/open?id=' + DOC_ID,
                'read drive https://drive.google.com/uc?id=' + DOC_ID + '&export=download',
                'Could you read drive "' + DOC_ID + '"'):
            with self.subTest(text=text):
                self.client.metadata_calls.clear()
                self.client.export_calls.clear()
                result = self.say(text)
                self.assertIn('First paragraph of the doc.', result)
                self.assertEqual(self.client.metadata_calls, [DOC_ID])

    def test_wrong_mime_returns_no_content(self):
        self.client.meta['mimeType'] = 'application/pdf'
        self.client.content = 'this binary payload must not leak'
        result = self.say('read drive ' + DOC_ID)
        self.assertIn('not a Google Doc or plain text', result)
        self.assert_failure(result)
        self.assertNotIn('this binary payload must not leak', result)
        self.assertFalse(self.client.export_calls)
        self.assertFalse(self.client.download_calls)
        self.assertFalse(self.client.writes)

    def test_inaccessible_id_is_not_an_empty_file(self):
        self.client.error = 'That Drive file could not be read; no content was returned.'
        result = self.say('read drive ' + DOC_ID)
        self.assertEqual(result, self.client.error)
        self.assert_failure(result)
        self.assertFalse(self.client.export_calls)
        self.assertFalse(self.client.download_calls)

    def test_oversized_output_is_truncated_without_claiming_the_whole_file(self):
        self.client.content = 'word ' * ((EXCERPT_LIMIT // 5) + 40)
        result = self.say('read drive ' + DOC_ID)
        self.assertIn('[Excerpt truncated.]', result)
        excerpt = result.split('\n\n', 1)[1].replace('\n[Excerpt truncated.]', '')
        self.assertLessEqual(len(excerpt), EXCERPT_LIMIT)
        self.assertIn('Google Drive: Proposal notes', result)

    def test_auth_failure_is_plain_needs_google_auth(self):
        self.client.error = NEEDS_AUTH
        result = self.say('read drive ' + DOC_ID)
        self.assertEqual(result, NEEDS_AUTH)
        self.assert_failure(result)
        self.assertFalse(self.client.export_calls)
        self.assertFalse(self.client.download_calls)
        self.assertFalse(self.client.writes)

    def test_active_hold_is_checked_before_auth_or_network(self):
        import chat_intent
        self.state = chat_intent.new_state()
        chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        with patch.object(self.client, 'configured') as configured, \
                patch.object(self.client, 'metadata') as metadata, \
                patch.object(self.client, 'export_text') as export_text, \
                patch.object(self.client, 'download_text') as download_text:
            for text in ('read drive ' + DOC_ID, 'read google doc https://docs.google.com/document/d/' + DOC_ID + '/edit'):
                self.assertIn('On hold:', self.say(text))
            configured.assert_not_called()
            metadata.assert_not_called()
            export_text.assert_not_called()
            download_text.assert_not_called()
        self.assertFalse(self.client.writes)

    def test_no_write_or_share_calls_on_success_or_failure(self):
        self.say('read drive ' + DOC_ID)
        self.client.meta['mimeType'] = 'image/png'
        self.say('read drive ' + DOC_ID)
        self.client.error = NEEDS_AUTH
        self.say('read drive ' + DOC_ID)
        self.assertFalse(self.client.writes)
        self.assertFalse(hasattr(self.actions, 'share'))
        self.assertFalse(callable(getattr(self.client, 'permissions', None)))

    def test_no_cross_conversation_leakage(self):
        first = self.say('read drive ' + DOC_ID, cid='alpha')
        other = FakeDrive()
        other.meta = {
            'id': OTHER_ID,
            'name': 'Other chat notes',
            'mimeType': TEXT_MIME,
            'modifiedTime': '2026-10-11T12:00:00.000Z',
            'webViewLink': 'https://drive.google.com/file/d/' + OTHER_ID + '/view',
        }
        other.content = 'CROSS-CONVERSATION-SECRET'
        leaked = DriveRead(other).handle('read drive ' + OTHER_ID, 'beta', str(uuid.uuid4()), self.state)
        self.assertIn('CROSS-CONVERSATION-SECRET', leaked)
        self.assertNotIn('CROSS-CONVERSATION-SECRET', first)
        self.assertNotIn('Other chat notes', first)
        restored = DriveRead(self.client)
        again = restored.handle('drive help', 'alpha', str(uuid.uuid4()), self.state)
        self.assertEqual(again, HELP)
        self.assertNotIn('CROSS-CONVERSATION-SECRET', again)
        self.assertFalse(getattr(self.actions, '_cache', None))
        self.assertFalse(list(self.root.rglob('*')))

    def test_metadata_mismatch_and_invalid_payloads_never_claim_success(self):
        self.client.metadata = Mock(return_value={'id': 'wrong', 'name': 'X', 'mimeType': DOC_MIME,
                                                  'modifiedTime': '2026-10-10T18:00:00Z'})
        result = self.say('read drive ' + DOC_ID)
        self.assertIn('invalid file metadata', result)
        self.assert_failure(result)
        self.assertFalse(self.client.export_calls)
        for payload in ({}, {'id': DOC_ID, 'name': 1, 'mimeType': DOC_MIME, 'modifiedTime': '2026-10-10T18:00:00Z'},
                        {'id': DOC_ID, 'name': 'X', 'mimeType': DOC_MIME, 'modifiedTime': 'not-a-time'}):
            self.client.metadata = Mock(return_value=payload)
            self.assert_failure(self.say('read drive ' + DOC_ID))

    def test_folders_spreadsheets_and_unknown_text_are_not_reads(self):
        self.assertIsNone(self.say('read file ~/Documents/notes.txt'))
        self.assertIsNone(self.say('show my calendar today'))
        self.assertIn('folders, spreadsheets, and slides', self.say(
            'read drive https://drive.google.com/drive/folders/' + DOC_ID))
        self.assertIn('I need a Google Drive file ID', self.say('read drive'))
        self.assertEqual(self.say('drive help'), HELP)
        self.assertFalse(self.client.configured_calls)
        self.assertFalse(self.client.metadata_calls)

    def test_constructed_source_link_when_web_view_is_absent(self):
        self.client.meta['webViewLink'] = None
        result = self.say('read drive ' + DOC_ID)
        self.assertIn('Source: https://drive.google.com/file/d/' + DOC_ID + '/view', result)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'oauth.json'
        self.path.write_text(json.dumps(dict(type='authorized_user', client_id='client',
                                             client_secret='private', refresh_token='refresh')))
        self.path.chmod(0o600)
        self.transport = Mock(side_effect=[
            {'access_token': 'access'},
            {'id': DOC_ID, 'name': 'Doc', 'mimeType': DOC_MIME,
             'modifiedTime': '2026-10-10T18:00:00Z',
             'webViewLink': 'https://docs.google.com/document/d/' + DOC_ID + '/edit'},
            {'access_token': 'access'},
            'Exported document text',
        ])
        self.client = GoogleDrive(self.path, self.transport)

    def test_credentials_are_read_lazily_and_oauth_is_injected(self):
        self.client.configured()
        self.transport.assert_not_called()
        meta = self.client.metadata(DOC_ID)
        self.assertEqual(meta['id'], DOC_ID)
        text = self.client.export_text(DOC_ID)
        self.assertEqual(text, 'Exported document text')
        oauth, metadata, oauth2, export = self.transport.call_args_list
        self.assertEqual(oauth.args[0], 'https://oauth2.googleapis.com/token')
        self.assertEqual(oauth.kwargs['data']['grant_type'], 'refresh_token')
        self.assertTrue(oauth.kwargs['form'])
        self.assertEqual(oauth2.args[0], oauth.args[0])
        self.assertIn('/drive/v3/files/' + DOC_ID, metadata.args[0])
        self.assertIn('fields=', metadata.args[0])
        self.assertNotIn('permissions', metadata.args[0])
        self.assertEqual(metadata.kwargs['headers'], {'Authorization': 'Bearer access'})
        self.assertTrue(metadata.kwargs['as_json'])
        self.assertIn('/export?', export.args[0])
        self.assertIn('mimeType=text%2Fplain', export.args[0])
        self.assertFalse(export.kwargs['as_json'])
        self.assertEqual(self.path.read_text().count('refresh'), 2)

    def test_plain_text_download_uses_alt_media_and_never_writes(self):
        self.transport.side_effect = [
            {'access_token': 'access'},
            'plain file',
        ]
        self.assertEqual(self.client.download_text(TEXT_ID), 'plain file')
        url = self.transport.call_args.args[0]
        self.assertIn('alt=media', url)
        self.assertIn('/drive/v3/files/' + TEXT_ID, url)
        self.assertNotIn('/permissions', url)
        self.assertNotIn('/copy', url)
        self.assertIsNone(self.transport.call_args.kwargs.get('data'))

    def test_explicit_drive_credentials_do_not_fall_back_to_calendar_or_adc(self):
        home = Path(self.tmp.name)
        calendar = home / '.config/webbob/google-calendar.json'
        adc = home / '.config/gcloud/application_default_credentials.json'
        calendar.parent.mkdir(parents=True)
        adc.parent.mkdir(parents=True)
        calendar.write_text(self.path.read_text())
        adc.write_text(self.path.read_text())
        calendar.chmod(0o600)
        adc.chmod(0o600)
        client = GoogleDrive(transport=self.transport)
        with patch('drive_read.Path.home', return_value=home), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
                client.configured()
            dedicated = home / '.config/webbob/google-drive.json'
            self.path.replace(dedicated)
            client.configured()
            missing = home / 'missing-drive.json'
            with patch.dict(os.environ, {'BOB_GOOGLE_DRIVE_CREDENTIALS': str(missing)}):
                with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
                    client.configured()
        self.transport.assert_not_called()

    def test_missing_insecure_symlink_invalid_and_service_credentials_need_auth(self):
        for value in ({}, {'type': 'service_account'}, [], {'client_id': 'secret'}):
            self.path.write_text(json.dumps(value))
            with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
                self.client.configured()
        self.path.write_text(json.dumps(dict(type='authorized_user', client_id='client',
                                             client_secret='private', refresh_token='refresh')))
        self.path.chmod(0o644)
        with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
            self.client.configured()
        self.path.unlink()
        with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
            self.client.configured()
        self.path.symlink_to(self.path.parent / 'absent')
        with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
            self.client.configured()
        self.transport.assert_not_called()

    def test_missing_access_token_needs_auth(self):
        self.transport.side_effect = [{}]
        with self.assertRaisesRegex(DriveError, NEEDS_AUTH):
            self.client.metadata(DOC_ID)

    def test_transport_is_bounded_no_proxy_no_redirect_no_retry_and_sanitizes_errors(self):
        response = Mock(status=200, headers={'Content-Length': '12'})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"id": "ok"}'
        opener = Mock()
        opener.open.return_value = response
        with patch('drive_read.urllib.request.build_opener', return_value=opener) as factory:
            self.assertEqual(request('https://www.googleapis.com/drive/v3/files/' + DOC_ID), {'id': 'ok'})
            self.assertEqual(factory.call_args.args[0].proxies, {})
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 10)
            self.assertEqual(response.read.call_args.args, (BODY_LIMIT + 1,))
            with self.assertRaises(DriveError):
                factory.call_args.args[1].redirect_request(None)
            for status, expected in ((401, NEEDS_AUTH), (403, NEEDS_AUTH),
                                     (404, 'could not be read'), (500, 'no content was verified')):
                opener.open.side_effect = urllib.error.HTTPError('secret-url', status, 'secret-body', {}, io.BytesIO())
                with self.assertRaises(DriveError) as error:
                    request('https://www.googleapis.com/drive/v3/files/' + DOC_ID)
                self.assertNotIn('secret', str(error.exception))
                self.assertIn(expected, str(error.exception))
                self.assertNotIn('empty', str(error.exception).lower())
        with self.assertRaises(DriveError):
            request('http://attacker.invalid')
        with self.assertRaises(DriveError):
            request('https://www.googleapis.com/drive/v3/files/' + DOC_ID + '/permissions',
                    data={'role': 'writer'})
        with self.assertRaises(DriveError):
            request('https://www.googleapis.com/calendar/v3/calendars/primary/events')

    def test_oversized_http_body_and_redirect_never_verify_content(self):
        response = Mock(status=200, headers={'Content-Length': str(BODY_LIMIT + 1)})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch('drive_read.urllib.request.build_opener', return_value=opener):
            response.read.return_value = b'x' * (BODY_LIMIT + 1)
            with self.assertRaisesRegex(DriveError, 'no content was verified'):
                request('https://www.googleapis.com/drive/v3/files/' + DOC_ID, as_json=False)
            response.read.return_value = b'[]'
            response.headers = {'Content-Length': '2'}
            with self.assertRaisesRegex(DriveError, 'no content was verified'):
                request('https://www.googleapis.com/drive/v3/files/' + DOC_ID)

    def test_short_partial_and_broken_chunked_bodies_are_not_complete_exports(self):
        response = Mock(status=200, headers={})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'partial'
        opener = Mock(open=Mock(return_value=response))
        with patch('drive_read.urllib.request.build_opener', return_value=opener):
            for status, headers in ((200, {'Content-Length': '900'}), (206, {}),
                                    (200, {'Content-Range': 'bytes 0-6/900'}),
                                    (200, {'Content-Length': 'invalid'})):
                response.status, response.headers = status, headers
                with self.subTest(status=status, headers=headers), self.assertRaises(DriveError):
                    request('https://www.googleapis.com/drive/v3/files/' + DOC_ID + '/export', as_json=False)
            response.status, response.headers = 200, {'Transfer-Encoding': 'chunked'}
            response.read.side_effect = http.client.IncompleteRead(b'partial')
            with self.assertRaises(DriveError):
                request('https://www.googleapis.com/drive/v3/files/' + DOC_ID + '/export', as_json=False)
            response.read.side_effect = None
            response.headers = {'Content-Length': '7'}
            self.assertEqual(request('https://www.googleapis.com/drive/v3/files/' + DOC_ID + '/export', as_json=False), 'partial')

    def test_http_framing_requires_length_or_complete_chunks(self):
        # Exercise the real HTTP reader entirely in memory: no sockets/OAuth.
        cases = (
            (b'Content-Length: 7\r\n', b'content', 'content'),
            (b'Transfer-Encoding: chunked\r\n', b'7\r\ncontent\r\n0\r\n\r\n', 'content'),
            (b'Transfer-Encoding: chunked\r\n', b'7\r\ncontent\r\n', None),
            (b'Transfer-Encoding: chunked\r\n', b'9\r\nshort', None),
            (b'', b'partial', None),
            (b'Content-Length: 90\r\n', b'partial', None),
            (b'Content-Length: 0\r\n', b'', ''),
        )
        for headers, body, expected in cases:
            with self.subTest(headers=headers, body=body):
                wire = io.BytesIO(b'HTTP/1.1 200 OK\r\n' + headers + b'\r\n' + body)
                response = http.client.HTTPResponse(Mock(makefile=Mock(return_value=wire)))
                response.begin()
                opener = Mock(open=Mock(return_value=response))
                with patch('drive_read.urllib.request.build_opener', return_value=opener):
                    if expected is None:
                        with self.assertRaisesRegex(DriveError, 'no content was verified'):
                            request('https://www.googleapis.com/drive/v3/files/' + DOC_ID, as_json=False)
                    else:
                        self.assertEqual(request('https://www.googleapis.com/drive/v3/files/' + DOC_ID,
                                                 as_json=False), expected)

    def test_parse_target_rejects_non_drive_hosts_and_folders(self):
        self.assertEqual(parse_target(DOC_ID), DOC_ID)
        with self.assertRaises(DriveError):
            parse_target('https://evil.example/document/d/' + DOC_ID)
        with self.assertRaises(DriveError):
            parse_target('https://drive.google.com/drive/folders/' + DOC_ID)


class RoutingTests(DriveFixture):
    def setUp(self):
        super().setUp()
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'chat', self.root, self.providers, texting=Texting(Mock(), Mock()),
                         reminder_notifier=Mock(), calendar=Mock(handle=Mock(return_value=None)),
                         drive=self.actions)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def submit(self, text, cid=None):
        with patch('app.parse_work', side_effect=AssertionError('Entered generic queue')):
            return self.chat.submit(cid or self.cid, text, str(uuid.uuid4()), actor='owner')['messages'][-1]

    def test_drive_read_is_direct_and_does_not_call_models_or_jobs(self):
        response = self.submit('read drive ' + DOC_ID)
        self.assertEqual(response['provider'], 'drive')
        self.assertIn('First paragraph of the doc.', response['content'])
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.client.writes)
        self.assertTrue(response['private_memory'])
        self.assertNotIn('First paragraph of the doc.', json.dumps(Texting.provider_view(self.chat.get(self.cid))))
        self.assertEqual(self.chat.coordination_records(self.chat.get(self.cid)), [])

    def test_credentials_never_reach_submit_response_or_persisted_history(self):
        # Keep the real receipt, Redactor and save paths, with a temporary root
        # and injected Drive client. No actual credential file is read.
        for mime in (DOC_MIME, TEXT_MIME):
            for body in SECRET_BODIES:
                with self.subTest(mime=mime, body=body[-80:]):
                    self.client.meta['mimeType'] = mime
                    self.client.content = body
                    saved = []
                    real_save = self.chat.save

                    def capture(conversation):
                        saved.append(copy.deepcopy(conversation))
                        return real_save(conversation)

                    with patch.object(self.chat, 'save', side_effect=capture):
                        response = self.submit('read drive ' + DOC_ID)
                    self.assertEqual(response['provider'], 'drive')
                    self.assertIn('Credential content refused', response['content'])
                    surfaces = [json.dumps(response), json.dumps(saved),
                                json.dumps(self.chat.get(self.cid)),
                                (self.chat.state / (self.cid + '.json')).read_text()]
                    for surface in surfaces:
                        self.assertNotIn('fixture-', surface)
                        self.assertNotIn('ordinary prose', surface)
                    self.assertTrue(saved)
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.client.writes)

    def test_needs_auth_is_direct_and_never_fabricates_content(self):
        self.client.error = NEEDS_AUTH
        response = self.submit('read google doc https://docs.google.com/document/d/' + DOC_ID + '/edit')
        self.assertEqual(response['provider'], 'drive')
        self.assertEqual(response['content'], NEEDS_AUTH)
        self.assert_failure(response['content'])
        self.assertFalse(self.providers.calls)
        self.assertFalse(self.client.export_calls)

    def test_saved_hold_blocks_drive_in_chat_before_auth(self):
        self.chat.submit(self.cid, 'Hold all work', str(uuid.uuid4()))
        before = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
        with patch.object(self.client, 'configured') as configured:
            self.assertIn('On hold:', self.submit('read drive ' + DOC_ID)['content'])
            configured.assert_not_called()
        self.assertEqual(self.chat.get(self.cid)['intent_state'], before)
        self.assertFalse(self.client.metadata_calls)

    def test_conversations_do_not_share_drive_excerpts(self):
        first = self.submit('read drive ' + DOC_ID)
        other = self.chat.new_conversation()['id']
        self.client.meta = {
            'id': OTHER_ID,
            'name': 'Beta only',
            'mimeType': TEXT_MIME,
            'modifiedTime': '2026-10-11T01:00:00Z',
            'webViewLink': 'https://drive.google.com/file/d/' + OTHER_ID + '/view',
        }
        self.client.content = 'BETA-ONLY-SECRET'
        second = self.submit('read drive ' + OTHER_ID, cid=other)
        self.assertNotIn('BETA-ONLY-SECRET', first['content'])
        self.assertNotIn('Beta only', first['content'])
        self.assertIn('BETA-ONLY-SECRET', second['content'])
        self.assertNotIn('BETA-ONLY-SECRET', self.chat.get(self.cid)['messages'][-1]['content'])

    def test_configured_drive_credentials_reject_local_file_operations(self):
        home = self.root / 'home'
        (home / 'Documents').mkdir(parents=True)
        target = home / 'Documents/google-drive.json'
        secret = json.dumps(dict(type='authorized_user', client_id='fixture-client',
                                 client_secret='fixture-oauth-secret', refresh_token='fixture-refresh-secret'))
        files = LocalFiles(home)
        actions = LocalTasks(self.root / 'state', files=files,
                             search=Mock(side_effect=AssertionError('search')), root=self.root)
        files.protected = actions.protected_paths
        state = {'holds': {}, 'last_permission': None}
        for configured in (str(target), '~/Documents/google-drive.json'):
            with self.subTest(configured=configured), patch.dict(
                    os.environ, {'BOB_GOOGLE_DRIVE_CREDENTIALS': configured, 'HOME': str(home)}):
                self.assertIn('outside the local file allowlist',
                              actions.handle(f'create file {target}: unsafe', 'chat', str(uuid.uuid4()), state))
                self.assertFalse(target.exists())
                target.write_text(secret)
                target.chmod(0o600)
                self.assertIn('outside the local file allowlist',
                              actions.handle(f'read file {target}', 'chat', str(uuid.uuid4()), state))
                with self.assertRaises(LocalTaskError):
                    actions.validate_routine(f'terminal: cat {target}')
                self.assertEqual(target.read_text(), secret)
                target.unlink()


if __name__ == '__main__':
    unittest.main()
