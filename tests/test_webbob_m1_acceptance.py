"""Exercise staging probes against actual isolated Chat and adversarial HTTP."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from unittest.mock import patch

from app import BUILD, Server
import test_webchat as harness
from tools.webbob_m1_acceptance import authenticated_probe, probe, target


class AcceptanceTests(harness.Fixture):
    def setUp(self):
        super().setUp()
        self.server = Server(('127.0.0.1', 0), self.chat)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        super().tearDown()

    def test_actual_runtime_build_and_auth_are_checked_without_login_or_model(self):
        result = probe(self.url, BUILD['sha'])
        self.assertTrue(result['staging_probes_passed'], result)
        self.assertEqual(result['observed_sha'], BUILD['sha'])
        self.assertEqual([c['status'] for c in result['checks']], [200, 200, 401, 401, 401])
        self.assertEqual(result['authenticated_phone_acceptance'], 'not exercised')
        self.assertFalse(result['activation_authorized'])
        self.assertFalse(self.chat.sessions)
        self.assertFalse(self.fake.calls)
        self.assertFalse(self.chat.history(self.identifier)['messages'])

    def test_reachable_old_build_is_not_candidate_acceptance(self):
        selected = 'a' * 40 if BUILD['sha'] != 'a' * 40 else 'b' * 40
        result = probe(self.url, selected)
        self.assertFalse(result['staging_probes_passed'])
        self.assertFalse(result['checks'][0]['ok'])
        self.assertEqual(result['observed_sha'], BUILD['sha'])

    def test_authenticated_reads_use_existing_session_without_printing_private_data(self):
        token = self.chat.login(self.chat.password)
        session = self.root / 'probe-session'
        session.write_text(token)
        session.chmod(0o600)
        before = self.chat.history(self.identifier)
        result = authenticated_probe(self.url, BUILD['sha'], session)
        self.assertTrue(result['authenticated_read_probes_passed'], result)
        self.assertNotIn(token, str(result))
        self.assertNotIn(self.chat.authenticate('bob_session=' + token)['csrf'], str(result))
        self.assertEqual(result['authenticated_phone_acceptance'], 'not exercised')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(self.chat.history(self.identifier), before)
        self.assertFalse(self.fake.calls)

    def test_mismatched_candidate_never_reads_session_file(self):
        selected = 'a' * 40 if BUILD['sha'] != 'a' * 40 else 'b' * 40
        with patch('os.open', side_effect=AssertionError('credential read')):
            result = authenticated_probe(self.url, selected, '/does-not-exist')
        self.assertFalse(result['authenticated_read_probes_passed'])

    def test_session_file_permissions_header_injection_and_expired_session_fail_closed(self):
        session = self.root / 'probe-session'
        session.write_text('a' * 43)
        session.chmod(0o644)
        with self.assertRaises(ValueError):
            authenticated_probe(self.url, BUILD['sha'], session)
        session.chmod(0o600)
        session.write_text('a' * 43 + '\r\nX-Injected: yes')
        with self.assertRaises(ValueError):
            authenticated_probe(self.url, BUILD['sha'], session)
        session.write_text('a' * 43)
        result = authenticated_probe(self.url, BUILD['sha'], session)
        self.assertFalse(result['authenticated_read_probes_passed'])
        self.assertTrue(all(row['status'] == 401 for row in result['authenticated_checks']))
        link = self.root / 'probe-session-link'
        link.symlink_to(session)
        with self.assertRaises(ValueError):
            authenticated_probe(self.url, BUILD['sha'], link)

    def test_invalid_and_credential_bearing_targets_fail_before_network(self):
        for url in ('https://user:password@host.ts.net/', 'https://host.ts.net/?token=x',
                    'https://example.com', 'http://host.ts.net', self.url + '/login',
                    'https://host.ts.net/#token', 'https://host.ts.net:bad'):
            with self.subTest(url=url), patch('http.client.HTTPConnection') as connection:
                with self.assertRaises(ValueError):
                    probe(url, 'a' * 40)
                connection.assert_not_called()
        for sha in ('abc1234', 'A' * 40, '', None):
            with self.assertRaises(ValueError):
                probe(self.url, sha)
        self.assertEqual(target('https://host.tail.ts.net/'), ('https', 'host.tail.ts.net', None))

    def test_redirect_is_not_followed_and_remote_body_is_never_reported(self):
        paths = []

        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                paths.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/private-side-effect')
                self.end_headers()
                self.wfile.write(b'private-response-canary-7304')

        server = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = probe('http://127.0.0.1:' + str(server.server_port), 'a' * 40)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
        self.assertFalse(result['staging_probes_passed'])
        self.assertEqual(paths, [row['path'] for row in result['checks']])
        self.assertNotIn('/private-side-effect', paths)
        self.assertNotIn('private-response-canary-7304', str(result))
