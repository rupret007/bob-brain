"""Private release-identity fixtures; no real HTTP, screen, service or credentials."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error


spec = importlib.util.spec_from_file_location('webbob_start_identity', Path(__file__).with_name('start.py'))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

BUILD = dict(sha='a' * 40, built_at='2026-09-29T00:00:00+00:00')


class Response(io.BytesIO):
    def __init__(self, raw=b'', status=200, marker='1'):
        super().__init__(raw)
        self.status = status
        self.headers = {'X-Bob-Webchat': marker}
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class StartupIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='webbob-start-identity-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.code = self.root / 'selected code'
        self.code.mkdir()
        self.state = self.root / 'conductor/state'
        self.state.mkdir(parents=True)
        self.manifest = self.code / 'webbob-build.json'
        self.manifest.write_text(json.dumps(BUILD))
        self.pin = self.state / 'webchat-code-root'
        self.pin.write_text(str(self.code) + '\n')
        self.addCleanup(os.umask, os.umask(0o077))
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        self.output = contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))
        contexts.enter_context(patch.dict(os.environ, {'BOB_ROOT': str(self.root)}, clear=True))
        # Deliberately not the selected application's directory.
        contexts.enter_context(patch.object(launcher, 'HERE', self.root / 'old code/webchat'))
        self.run = contexts.enter_context(patch.object(launcher.subprocess, 'run'))
        contexts.enter_context(patch.object(launcher.time, 'sleep'))
        self.opener = Mock()
        contexts.enter_context(patch.object(launcher.urllib.request, 'build_opener', return_value=self.opener))
        self.fallback = contexts.enter_context(patch.object(launcher, 'load_build'))

    def responses(self, raw=None, *, status=200, marker='1'):
        if raw is None:
            raw = json.dumps(dict(name='Web Bob', **BUILD)).encode()
        login = Response()
        denied = urllib.error.HTTPError(launcher.URL + '/api', 401, 'Unauthorized',
                                        {'X-Bob-Webchat': '1'}, io.BytesIO())
        version = Response(raw, status, marker)
        self.opener.open.side_effect = [login, denied, version]
        return login, denied, version

    def assert_refused_without_probe(self):
        self.assertEqual(launcher.main(), 1)
        self.opener.open.assert_not_called()
        self.run.assert_not_called()

    def test_selected_pin_not_launcher_directory_sets_identity(self):
        login, denied, version = self.responses()
        self.assertEqual(launcher.main(), 0)
        self.assertEqual([call.args[0] for call in self.opener.open.call_args_list],
                         [launcher.URL + path for path in ('/login', '/api', '/api/version')])
        self.assertTrue(all(call.kwargs['timeout'] == 2 for call in self.opener.open.call_args_list))
        self.assertEqual(version.read_sizes, [launcher.IDENTITY_LIMIT + 1])
        self.assertTrue(login.closed and denied.closed and version.closed)
        self.run.assert_not_called()
        self.fallback.assert_not_called()

    def test_webchat_pin_takes_precedence_over_unused_invalid_dispatch(self):
        (self.state / 'dispatch-code-root').write_text('invalid-unused-fallback\n')
        self.assertEqual(launcher.selected_identity(self.root), BUILD)

    def test_dispatch_and_unpinned_fallbacks_select_their_own_build(self):
        self.pin.rename(self.state / 'dispatch-code-root')
        self.assertEqual(launcher.selected_identity(self.root), BUILD)
        (self.state / 'dispatch-code-root').unlink()
        other = dict(BUILD, sha='b' * 40)
        (self.root / 'conductor/webbob-build.json').write_text(json.dumps(other))
        self.assertEqual(launcher.selected_identity(self.root), other)

    def test_invalid_selected_pins_refuse_before_http_or_screen(self):
        for value in ('', '\n', 'relative/code\n', str(self.code) + '\nextra', str(self.code) + '\0'):
            with self.subTest(value=value):
                self.pin.write_text(value)
                self.assert_refused_without_probe()
        self.assertNotIn(str(self.root), self.output.getvalue())

    def test_unsafe_pin_and_manifest_reads_are_bounded(self):
        for path in (self.pin, self.manifest):
            original = path.read_bytes()
            for kind in ('dangling-link', 'fifo', 'oversized'):
                with self.subTest(file=path.name, kind=kind):
                    path.unlink()
                    if kind == 'dangling-link':
                        path.symlink_to(self.root / 'absent-target')
                    elif kind == 'fifo':
                        os.mkfifo(path, 0o600)
                    else:
                        path.write_bytes(b'x' * (launcher.IDENTITY_LIMIT + 1))
                    self.assert_refused_without_probe()
                    path.unlink()
                    path.write_bytes(original)

    def test_invalid_manifests_cannot_borrow_fallback_identity(self):
        for value in ('{', '[]', '{}', json.dumps(dict(BUILD, sha='unknown')),
                      json.dumps(dict(BUILD, sha=123)), json.dumps(dict(BUILD, built_at='unknown'))):
            with self.subTest(value=value):
                self.manifest.write_text(value)
                self.assert_refused_without_probe()
        self.fallback.assert_not_called()

    def test_missing_manifest_uses_existing_anchored_checkout_identity(self):
        self.manifest.unlink()
        self.fallback.return_value = BUILD
        self.assertEqual(launcher.selected_identity(self.root), BUILD)
        self.fallback.assert_called_once_with(self.code)
        self.fallback.return_value = dict(sha='unknown', built_at='unknown')
        self.assert_refused_without_probe()

    def test_wrong_sha_or_build_time_refuses_without_touching_existing_server(self):
        for changes in (dict(sha='b' * 40), dict(built_at='2026-09-28T00:00:00+00:00')):
            with self.subTest(changes=changes):
                self.responses(json.dumps(dict(name='Web Bob', **dict(BUILD, **changes))).encode())
                self.assertEqual(launcher.main(), 1)
                self.run.assert_not_called()
        self.assertNotIn('healthy', self.output.getvalue())
        self.assertIn('release identity cannot be verified', self.output.getvalue())

    def test_invalid_or_oversized_version_body_refuses_without_screen(self):
        for raw in (b'{', b'[]', b'{}', b'x' * (launcher.IDENTITY_LIMIT + 1),
                    json.dumps(dict(name='different-service', **BUILD)).encode()):
            with self.subTest(raw_length=len(raw)):
                self.responses(raw)
                self.assertEqual(launcher.main(), 1)
                self.run.assert_not_called()

    def test_version_response_requires_bob_marker_and_success_status(self):
        for status, marker in ((503, '1'), (200, '0')):
            self.responses(status=status, marker=marker)
            self.assertEqual(launcher.main(), 1)
            self.run.assert_not_called()

    def test_version_unavailable_after_bob_answers_does_not_start_another_server(self):
        for error in (TimeoutError('private-fixture-detail'),
                      urllib.error.URLError('private-fixture-detail')):
            login, denied, version = self.responses()
            version.close()
            self.opener.open.side_effect = [login, denied, error]
            self.assertEqual(launcher.main(), 1)
            self.run.assert_not_called()
        self.assertNotIn('private-fixture-detail', self.output.getvalue())

    def test_readiness_wrong_release_stops_after_one_launch(self):
        login, denied, version = self.responses(json.dumps(dict(name='Web Bob', **dict(BUILD, sha='b' * 40))).encode())
        self.opener.open.side_effect = [urllib.error.URLError('offline'), login, denied, version]
        self.run.return_value = subprocess.CompletedProcess('screen', 1, 'No Sockets found in /fixture.', '')
        self.assertEqual(launcher.main(), 1)
        self.assertEqual([call.args[0][1] for call in self.run.call_args_list], ['-ls', '-dmS'])
        self.assertEqual(self.opener.open.call_count, 4)
        self.assertNotIn('Started', self.output.getvalue())

    def test_original_login_and_auth_boundary_checks_still_required(self):
        for responses in ([Response(marker='0')], [Response(), Response(status=200)],
                          [urllib.error.URLError('offline')]):
            self.opener.open.side_effect = responses
            self.assertFalse(launcher.healthy(BUILD))
        self.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
