"""Release failure behavior and evidence authority, without touching production."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import solo


class BridgeReplayTargetTests(unittest.TestCase):
    def test_excludes_short_codes_groups_and_mismatched_membership(self):
        for guid, addresses in (
            ('SMS;-;12345', ['12345']),
            ('iMessage;+;group', ['+12025550101']),
            ('iMessage;-;+12025550101', ['+12025550102']),
            ('iMessage;-;+12025550101', ['+12025550101', '+12025550102']),
            ('iMessage;-;bad@example', ['bad@example']),
        ):
            with self.subTest(guid=guid):
                self.assertFalse(solo.bridge_replay_target(dict(guid=guid, participants=[dict(address=a) for a in addresses])))

    def test_accepts_verified_direct_phone_or_email_membership(self):
        for service, address in (('SMS', '+12025550101'), ('iMessage', 'owner@example.com'), ('RCS', '+442079460123')):
            self.assertTrue(solo.bridge_replay_target(dict(guid=service+';-;'+address, participants=[dict(address=address)])))


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'record.json'
        self.record = dict(previous='b' * 40, sha='c' * 40, snapshots={'webchat': 'frozen-predecessor'})
        for name in ('require_disk_space', 'release_recovery', 'restart', 'versions'):
            p = patch.object(solo, name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.versions.return_value = {'local': {'sha': 'b' * 40}, 'public': {'sha': 'b' * 40}}

    def attempt(self, activate=None, live=None, **kw):
        solo.transaction(self.root, self.record, self.path, activate or Mock(),
                         live or Mock(return_value={'all_pass': True}), **kw)

    def test_requires_two_live_greens(self):
        live = Mock(return_value={'all_pass': True})
        self.attempt(live=live)
        self.assertEqual(live.call_count, 2)
        self.assertEqual(len(json.loads(self.path.read_text())['rounds']), 2)
        self.restart.assert_not_called()

    def test_second_live_failure_rolls_back_to_immediate_predecessor(self):
        with self.assertRaisesRegex(Exception, 'Live replay failed'):
            self.attempt(live=Mock(side_effect=[{'all_pass': True}, {'all_pass': False}]))
        self.restart.assert_called_once_with(self.root, self.record['snapshots'])
        self.versions.assert_called_with(self.root, 'b' * 40)
        self.assertFalse(json.loads(self.path.read_text())['all_pass'])

    def test_partial_startup_failure_also_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, 'startup'):
            self.attempt(activate=Mock(side_effect=RuntimeError('startup')))
        self.restart.assert_called_once()

    def test_disk_failure_before_activation_never_restarts(self):
        self.require_disk_space.side_effect = OSError('disk floor')
        activate = Mock()
        with self.assertRaises(OSError):
            self.attempt(activate=activate)
        activate.assert_not_called()
        self.restart.assert_not_called()

    def test_disk_failure_in_live_round_restores_first(self):
        self.require_disk_space.side_effect = [{}, OSError('disk floor')]
        with self.assertRaises(OSError):
            self.attempt()
        self.restart.assert_called_once()

    def test_final_evidence_write_failure_cannot_leave_candidate_live(self):
        def publish(path, value):
            if value.get('all_pass'):
                raise OSError('publish failed')
            solo.atomic_json(path, value)
        with self.assertRaises(OSError):
            self.attempt(publish=publish)
        self.restart.assert_called_once()

    def test_success_alias_failure_rolls_back(self):
        alias = self.root / 'latest.json'
        def publish(path, value):
            if path == alias:
                raise OSError('alias failed')
            solo.atomic_json(path, value)
        with self.assertRaises(OSError):
            self.attempt(publish=publish, final_path=alias)
        self.restart.assert_called_once()
        self.assertFalse(json.loads(self.path.read_text())['all_pass'])

    def test_keyboard_interrupt_rolls_back(self):
        with self.assertRaises(KeyboardInterrupt):
            self.attempt(live=Mock(side_effect=KeyboardInterrupt))
        self.restart.assert_called_once()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.log = self.folder / 'tests.log'
        self.log.write_text('Ran tests OK')
        names = {'webchat', 'services', 'reviews', 'release', 'eval', 'browser'}
        names.update(p.stem for p in (solo.CODE / 'webchat').glob('test_*.mjs'))
        self.check = dict(sha='a' * 40, feature='texting', all_pass=True, staging={'all_pass': True},
                          results={n: dict(exit=0, skipped=0, log=str(self.log), log_sha256=solo.digest(self.log)) for n in names})
        self.review = dict(sha='a' * 40, feature='texting', reviewer='Codex solo', verdict='PASS',
                           findings=['Inspected auth, durable consent, unknown outcome, rollback'])

    def verify(self):
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        return solo.verify_gates('a' * 40, 'texting', checks, review)

    def test_complete_evidence_passes_without_council(self):
        self.assertIn('self_review_sha256', self.verify())

    def attempts(self, states):
        for index, passed in enumerate(states, 1):
            folder = self.folder / f'attempt-{index:04d}'
            folder.mkdir()
            check = dict(self.check, all_pass=passed)
            solo.atomic_json(folder / 'checks.json', check)
        return folder / 'checks.json'

    def test_two_complete_latest_predeploy_greens_required(self):
        path = self.attempts([False, True, True])
        pair = solo.consecutive_checks('a' * 40, 'texting', path)
        self.assertEqual(len(pair), 2)
        self.assertEqual(pair[-1]['sha256'], solo.digest(path))

    def test_single_predeploy_green_is_not_enough(self):
        path = self.attempts([True])
        with self.assertRaisesRegex(Exception, 'Two consecutive'):
            solo.consecutive_checks('a' * 40, 'texting', path)

    def test_failure_between_predeploy_greens_is_not_skipped(self):
        path = self.attempts([True, False, True])
        with self.assertRaisesRegex(Exception, 'failed'):
            solo.consecutive_checks('a' * 40, 'texting', path)

    def test_earlier_green_pair_cannot_override_latest_failure(self):
        self.attempts([True, True, False])
        with self.assertRaisesRegex(Exception, 'latest'):
            solo.consecutive_checks('a' * 40, 'texting', self.folder / 'attempt-0002/checks.json')

    def test_both_predeploy_suite_hashes_are_rechecked(self):
        path = self.attempts([True, True])
        earlier = self.folder / 'attempt-0001/checks.json'
        check = json.loads(earlier.read_text())
        check['results']['webchat']['log_sha256'] = 'changed'
        solo.atomic_json(earlier, check)
        with self.assertRaisesRegex(Exception, 'changed'):
            solo.consecutive_checks('a' * 40, 'texting', path)

    def test_stale_candidate_review_rejected(self):
        self.review['sha'] = 'b' * 40
        with self.assertRaisesRegex(Exception, 'Stale'):
            self.verify()

    def test_cross_feature_evidence_rejected(self):
        self.check['feature'] = 'media'
        with self.assertRaisesRegex(Exception, 'wrong-feature'):
            self.verify()

    def test_missing_suite_rejected(self):
        del self.check['results']['services']
        with self.assertRaisesRegex(Exception, 'Missing'):
            self.verify()

    def test_voice_requires_audio_browser_and_js_suites(self):
        self.check['feature'] = self.review['feature'] = 'voice'
        self.check['results']['media-browser'] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_gates('a' * 40, 'voice', checks, review)

    def test_improve_requires_voice_availability_browser_without_replacing_real_audio(self):
        self.check['feature'] = 'improve'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser',
                     'remaining-browser', 'cold-browser', 'bridge-contract', 'jobs-results-browser', 'reply-lifecycle-browser'):
            self.check['results'][name] = self.check['results']['browser']
        sha = solo.andrea_pin()['sha']
        self.check['andrea'] = dict(sha=sha, results=[])
        solo.atomic_json(self.folder / 'bridge-contract.json', dict(all_pass=True, andrea_sha=sha, real_texts_sent=0))
        checks = self.folder / 'checks.json'
        solo.atomic_json(checks, self.check)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_checks('a' * 40, 'improve', checks)
        self.check['results']['voice-availability-browser'] = self.check['results']['browser']
        solo.atomic_json(checks, self.check)
        solo.verify_checks('a' * 40, 'improve', checks)
        del self.check['results']['voice-browser']
        solo.atomic_json(checks, self.check)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_checks('a' * 40, 'improve', checks)

    def test_instinct_requires_read_only_browser_proof(self):
        self.check['feature'] = self.review['feature'] = 'instinct'
        for name in ('media-browser', 'voice-js', 'voice-browser'):
            self.check['results'][name] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_gates('a' * 40, 'instinct', checks, review)

    def test_remaining_requires_reminder_browser_proof(self):
        self.check['feature'] = self.review['feature'] = 'remaining'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser'):
            self.check['results'][name] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_gates('a' * 40, 'remaining', checks, review)

    def test_bridge_cannot_release_without_pinned_andrea_evidence(self):
        self.check['feature'] = self.review['feature'] = 'bridge'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser', 'remaining-browser', 'bridge-contract'):
            self.check['results'][name] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Andrea exact-tip evidence missing'):
            solo.verify_gates('a' * 40, 'bridge', checks, review)

    def test_skipped_required_checks_rejected(self):
        self.check['results']['webchat']['skipped'] = 1
        with self.assertRaisesRegex(Exception, 'skipped'):
            self.verify()

    def test_improve_requires_jobs_result_browser_and_still_requires_real_voice(self):
        self.check['feature'] = 'improve'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser',
                     'remaining-browser', 'bridge-contract', 'cold-browser', 'jobs-results-browser',
                     'voice-availability-browser', 'reply-lifecycle-browser'):
            self.check['results'][name] = dict(self.check['results']['browser'])
        self.check['andrea'] = {'sha': solo.andrea_pin()['sha'], 'results': []}
        solo.atomic_json(self.folder / 'bridge-contract.json', dict(
            all_pass=True, andrea_sha=solo.andrea_pin()['sha'], real_texts_sent=0))
        checks = self.folder / 'checks.json'
        solo.atomic_json(checks, self.check)
        solo.verify_checks('a' * 40, 'improve', checks)
        for missing in ('jobs-results-browser', 'reply-lifecycle-browser', 'voice-browser'):
            with self.subTest(missing=missing):
                value = copy.deepcopy(self.check)
                del value['results'][missing]
                solo.atomic_json(checks, value)
                with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
                    solo.verify_checks('a' * 40, 'improve', checks)

    def test_changed_log_rejected(self):
        self.log.write_text('Different bytes')
        with self.assertRaisesRegex(Exception, 'changed'):
            self.verify()

    def test_unresolved_review_blocker_rejected(self):
        self.review['unresolved_blockers'] = ['Broken consent']
        with self.assertRaisesRegex(Exception, 'unresolved'):
            self.verify()


class MediaEvidenceTests(unittest.TestCase):
    def test_guessed_text_on_nonvision_fallback_is_not_live_vision_evidence(self):
        answer = dict(provider='codex', content='red note-token pdf-token', attachments=[dict(media_id='picture')])
        with self.assertRaisesRegex(Exception, 'vision provider'):
            solo.verify_media_answer(answer, 'note-token', 'pdf-token', 'picture', real=True)

    def test_attachment_extraction_warning_is_not_a_full_media_pass(self):
        answer = dict(provider='gemini', content='red note-token pdf-token\nAttachment notes: failed to decode',
                      attachments=[dict(media_id='picture')])
        with self.assertRaisesRegex(Exception, 'incomplete attachment'):
            solo.verify_media_answer(answer, 'note-token', 'pdf-token', 'picture', real=True)


class InstinctEvidenceTests(unittest.TestCase):
    def test_missing_mapping_is_not_a_live_pass(self):
        with patch.object(solo, 'submit', return_value=({}, dict(provider='instinct', content='Verified thread not found'))):
            with self.assertRaisesRegex(Exception, 'mapping/read is unavailable'):
                solo.instinct_replay(Mock(), 'conversation')

    def test_confirmable_instinct_draft_is_not_a_live_pass(self):
        digest = dict(provider='instinct', content='read from BlueBubbles\nBills / deadlines: 0\nSecurity: 0\nAppointments: 0')
        card = dict(text_draft=dict(state='pending', confirm_message='yes wbtxt-' + 'a' * 32))
        with patch.object(solo, 'submit', side_effect=[({}, digest), ({}, card)]):
            with self.assertRaisesRegex(Exception, 'send authority'):
                solo.instinct_replay(Mock(), 'conversation')


if __name__ == '__main__':
    unittest.main()
