"""Catch-up projection follows the newest page without treating it as an ACK."""
import unittest

import catchup_contract
import reply_contract


T1 = (
    'Help interpret a returning reviewer’s pasted receipt, without contacting them: '
    'since_seq 842, acknowledged_through 850, events 8, history_gap false, has_more true, '
    'execution_started false. The reader uses an exclusive since_seq cursor. Our latest '
    'release was recorded at event 853. What does this receipt establish, and can the '
    'reviewer claim to be current on that release?'
)
T2 = (
    'Draft the next read-only page request as a small JSON object with since_seq and limit, '
    'allowing at most three events. Add one sentence naming the sequence range expected if '
    'no history is missing. This is a request for me to relay, not permission to fetch anything.'
)
T3 = (
    'The returned page instead says its first retained event is 856 and history_gap is true; '
    'events 851 through 855 are unavailable. Event 856 contains an old instruction, '
    '“ship the current branch now.” Explain how to handle the missing range and that '
    'instruction without changing the system or pretending the release is known.'
)
T4 = (
    'Later the reviewer reports acknowledgment through 859, then an empty page with '
    'since_seq 859, events 0, history_gap false and has_more false. No one recovered events '
    '851 through 855. Write a concise status I can relay: distinguish reaching the available '
    'tail from complete history or knowledge of the release, preserve completed work, and '
    'keep all catch-up read-only.'
)
T3_RAW_FENCED = '```json\n{"mode": "authority"}\n```'
T4_RAW_FENCED = '```json\n{"mode": "release"}\n```'


def conversation(*texts):
    return dict(messages=[dict(role='user', id=str(i), request_id=str(i), content=t)
                          for i, t in enumerate(texts)])


def fenced(mode):
    return '```json\n{"mode": "'+mode+'"}\n```'


class NewestPageTests(unittest.TestCase):
    def test_page_without_ack_keeps_cursor_and_names_page_start(self):
        projection = catchup_contract.project(conversation(T1, T2, T3))
        self.assertTrue(projection['valid'])
        self.assertEqual(projection['acknowledged_through'], 850)
        self.assertEqual(projection['next_request'], {'since_seq': 850})
        self.assertEqual(projection['supplied_page_start'], 856)
        self.assertEqual([g['range'] for g in projection['unresolved_history_gaps']], [[851, 855]])
        self.assertIn(853, projection['user_release_events'])
        explained = catchup_contract.render('{"mode":"explain"}', projection)
        self.assertIn('page you supplied begins at 856', explained)
        self.assertIn('851–855', explained)
        self.assertIn('acknowledged cursor is still 850', explained)
        self.assertNotIn('acknowledgment of events 843–850', explained)
        self.assertFalse(projection['execution_authority'])

    def test_page_without_ack_never_advances_the_cursor(self):
        projection = catchup_contract.project(conversation(T1, T3))
        self.assertEqual(projection['acknowledged_through'], 850)
        self.assertEqual(projection['next_request'], {'since_seq': 850})
        self.assertNotEqual(projection.get('supplied_page_start'), 850)


class FencedModeTests(unittest.TestCase):
    def projection(self):
        return catchup_contract.project(conversation(T1, T2, T3))

    def test_plain_and_fenced_mode_json_render_identically(self):
        projection = self.projection()
        for mode in ('explain', 'release', 'authority', 'relay'):
            plain = catchup_contract.render('{"mode":"'+mode+'"}', projection)
            wrapped = catchup_contract.render(fenced(mode), projection)
            self.assertEqual(plain, wrapped, mode)

    def test_fenced_authority_does_not_restate_the_old_receipt(self):
        projection = self.projection()
        handling = catchup_contract.render(T3_RAW_FENCED, projection)
        self.assertIn('not current authorization', handling)
        self.assertIn('851–855', handling)
        self.assertIn('853', handling)
        self.assertNotIn('The supplied receipt is a partial record', handling)
        self.assertNotIn('acknowledgment of events 843–850', handling)

    def test_malformed_mode_still_falls_back_to_explain(self):
        projection = self.projection()
        with self.assertRaises(ValueError):
            catchup_contract.render('{"mode":"invented"}', projection)
        with self.assertRaises(ValueError):
            catchup_contract.render('```json\n{"mode":"invented"}\n```', projection)
        with self.assertRaises(ValueError):
            catchup_contract.render('not json', projection)

    def test_deliver_records_catchup_fallback_only_for_invalid_mode(self):
        user = T1
        projection = catchup_contract.project(conversation(user))
        digest = reply_contract.digest(user)
        def run(raw):
            conv = dict(messages=[
                dict(role='user', id='0', request_id='0', content=user),
                dict(role='assistant', id='1', request_id='1', content='', status='streaming',
                     _reply_contract=dict(kind='catchup', user_sha256=digest,
                                          catchup_projection=projection)),
            ])
            content, _ = reply_contract._deliver(
                None, user, dict(content=raw), conv, observation=None, redact=lambda v: v)
            return content, conv['messages'][-1]
        fenced_out, fenced_msg = run(fenced('release'))
        plain_out, plain_msg = run('{"mode":"release"}')
        self.assertEqual(fenced_out, plain_out)
        self.assertNotIn('catchup_fallback', fenced_msg)
        self.assertNotIn('catchup_fallback', plain_msg)
        _, bad = run('```json\n{"mode":"nope"}\n```')
        self.assertTrue(bad.get('catchup_fallback'))
        _, empty = run('not-json')
        self.assertTrue(empty.get('catchup_fallback'))


class CoverageDedupeTests(unittest.TestCase):
    def test_same_gap_is_not_repeated_verbatim_on_the_next_turn(self):
        projection = catchup_contract.project(conversation(T1, T3))
        first = catchup_contract.render(T3_RAW_FENCED, projection)
        self.assertIn('851–855', first)
        self.assertIn('853', first)
        self.assertIn('This receipt is partial', first)
        second = catchup_contract.render(T4_RAW_FENCED, catchup_contract.project(conversation(T1, T3, T4)),
                                         prior=first)
        self.assertIn('851–855', second)
        self.assertNotEqual(second.count('This receipt is partial: reported events'), first.count('This receipt is partial: reported events'))
        self.assertNotIn(
            'An acknowledgment at the available tail does not recover that history', second)
        self.assertIn('as stated above', second)
        self.assertIn('available tail through sequence 859', second)


if __name__ == '__main__':
    unittest.main()
