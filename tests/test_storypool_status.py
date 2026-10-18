from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from webbob.storypool_status import MAX_BYTES, _dashboard, collect_status


class StackStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.repo = self.root / 'install'
        self.data.mkdir()
        self.repo.mkdir()
        (self.data / 'conductor').mkdir()
        (self.data / 'dispatch').mkdir()
        self.now = 1700000000
        self.timestamp = datetime.fromtimestamp(self.now, timezone.utc).isoformat()
        self.dashboard = {'timestamp': self.timestamp, 'services': [{'name': 'Karen', 'status': 'running',
                          'details': 'api_key=private-fixture'}], 'jobs_stats': {'running': 2},
                          'auth': 'private-fixture', 'logs': 'private-fixture'}

    def collect(self, dashboard=None):
        with patch('webbob.storypool_status._dashboard', return_value=self.dashboard if dashboard is None else dashboard):
            return collect_status(self.data, self.repo, now=self.now)

    def test_reads_all_status_and_escalation_sources_without_mutation(self):
        (self.data / 'conductor/conductor-status.json').write_text(json.dumps(
            {'timestamp': self.timestamp, 'summary': {'executed_count': 1, 'anomalies': ['private-fixture']}}))
        (self.data / 'dispatch/dispatch-status.json').write_text(json.dumps(
            {'timestamp': self.timestamp, 'summary': {'dispatched': 2, 'skipped': 3, 'decisions': ['private-fixture']}}))
        for path in (self.data / 'NEEDS_JEFF.md', self.data / 'conductor/NEEDS_JEFF.md', self.repo / 'NEEDS_JEFF.md'):
            path.write_text('- Review billing limits\n')
        before = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        report = self.collect()
        after = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(report['execution_authority'])
        self.assertTrue(report['untrusted_observations'])
        self.assertEqual([row['state'] for row in report['files']], ['observed', 'observed'])
        self.assertEqual([row['freshness'] for row in report['files']], ['fresh', 'fresh'])
        self.assertEqual(len(report['needs_jeff']), 3)
        self.assertTrue(all(row['items'] == ['- Review billing limits'] for row in report['needs_jeff']))
        self.assertEqual(report['dashboard']['jobs_stats'], {'running': 2})
        self.assertNotIn('private-fixture', json.dumps(report))

    def test_missing_or_unavailable_is_not_healthy(self):
        with patch('webbob.storypool_status._dashboard', side_effect=OSError('private-fixture')):
            report = collect_status(self.data, self.repo, now=self.now)
        self.assertEqual(report['dashboard']['state'], 'unavailable')
        self.assertTrue(all(row['state'] == 'unavailable' for row in report['files'] + report['needs_jeff']))
        self.assertNotIn('private-fixture', json.dumps(report))

    def test_malformed_oversized_nonobject_and_symlink_files_are_unavailable(self):
        path = self.data / 'conductor/conductor-status.json'
        for raw in ('{', '[]', 'x' * (MAX_BYTES + 1)):
            path.write_text(raw)
            self.assertEqual(self.collect()['files'][0]['state'], 'unavailable')
        path.unlink()
        secret = self.data / 'credentials.key'
        secret.write_text('private-fixture')
        path.symlink_to(secret)
        self.assertEqual(self.collect()['files'][0]['state'], 'unavailable')
        self.assertNotIn('private-fixture', json.dumps(self.collect()))

    def test_status_symlink_directory_cannot_escape_to_config(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'conductor-status.json').write_text('private-fixture')
        (self.data / 'conductor').rmdir()
        (self.data / 'conductor').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.collect()['files'][0]['state'], 'unavailable')

    def test_needs_jeff_secret_lines_are_omitted(self):
        (self.data / 'NEEDS_JEFF.md').write_text('- Review runner billing\napi_key=private-fixture\nBearer private-fixture\n')
        result = self.collect()
        self.assertIn('- Review runner billing', result['needs_jeff'][0]['items'])
        self.assertNotIn('private-fixture', json.dumps(result))

    def test_stale_future_and_missing_timestamps_are_explicit(self):
        old = datetime.fromtimestamp(self.now - 901, timezone.utc).isoformat()
        future = datetime.fromtimestamp(self.now + 1, timezone.utc).isoformat()
        for timestamp, expected in ((old, 'stale'), (future, 'stale'), (None, 'unknown'), ('invalid', 'unknown')):
            dashboard = dict(self.dashboard, timestamp=timestamp)
            self.assertEqual(self.collect(dashboard)['dashboard']['freshness'], expected)

    def test_fixed_loopback_get_no_redirect_or_proxy(self):
        response = Mock(status=200)
        response.read.return_value = json.dumps(self.dashboard).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        with patch('http.client.HTTPConnection', return_value=connection) as constructor:
            self.assertEqual(_dashboard(8790), self.dashboard)
        constructor.assert_called_once_with('127.0.0.1', 8790, timeout=2)
        connection.request.assert_called_once_with('GET', '/api/data', headers={'Accept': 'application/json'})
        connection.close.assert_called_once()
        response.status = 302
        with patch('http.client.HTTPConnection', return_value=connection), self.assertRaises(ValueError):
            _dashboard(8790)
        self.assertEqual(connection.request.call_count, 2)

    def test_dashboard_oversize_and_invalid_payloads_are_unavailable(self):
        for data in ([], {'services': 'invalid'}):
            self.assertEqual(self.collect(data)['dashboard']['state'], 'unavailable')
        response = Mock(status=200)
        response.read.return_value = b'x' * (MAX_BYTES + 1)
        connection = Mock()
        connection.getresponse.return_value = response
        with patch('http.client.HTTPConnection', return_value=connection), self.assertRaises(ValueError):
            _dashboard(8790)


class OnDemandSkillTests(unittest.TestCase):
    def test_status_dates_are_validated_canonical_data(self):
        from webbob.storypool_status import _timestamp
        self.assertEqual(_timestamp('2026-10-18T19:11:32.123456Z'), '2026-10-18T19:11:32.123456+00:00')
        for value in (None, {}, 'password=fixture', '2026-10-18T19:11:32'):
            self.assertEqual(_timestamp(value), 'unknown')

    def test_three_skills_exist_are_explicit_only_and_read_only(self):
        root = Path(__file__).parents[1] / 'skills'
        for name in ('band-desk', 'director', 'stack-ops'):
            with self.subTest(name=name):
                skill = (root / name / 'SKILL.md').read_text()
                policy = (root / name / 'agents/openai.yaml').read_text()
                self.assertTrue(skill.startswith('---\nname: ' + name + '\n'))
                self.assertIn('allow_implicit_invocation: false', policy)
                self.assertIn('rad-dad-show-night', skill)
                self.assertIn('read', skill.lower())
                self.assertIn('Jeff', skill)
