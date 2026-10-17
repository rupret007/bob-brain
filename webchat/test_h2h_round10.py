"""Missing-evidence regressions; private stores, no model or transport calls.

Prompt checks establish delivered guidance, not generated answer quality.
"""
import unittest

import test_h2h_round4 as fixtures
import ledger
from task_dispatch import task_queue


class RoundTenTests(unittest.TestCase):
    setUp = fixtures.RoundFourTests.setUp
    say = fixtures.RoundFourTests.say
    policy = fixtures.RoundFourTests.policy

    def test_missing_document_clarification_is_compact_and_keeps_summary_scope(self):
        for ask in ('Summarize the report I shared last week.',
                    'Extract decisions from the missing meeting transcript.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('combine the missing-content limit with the request',
                             'Keep missing-document replies to two short sentences',
                             'ask for an attachment or pasted text',
                             'main points, plus decisions and action items if present',
                             'Use supplied document contents when available',
                             'do not invent file-retention or session-storage policies',
                             'Keep latest-file searches to one missing-location question'):
                    self.assertIn(part, rules)

    def test_clock_uses_known_context_without_assuming_location_or_current_time(self):
        for ask in ('What time is it in Seoul?',
                    'I am in Denver. What time is it in Madrid?',
                    'Convert 10 pm on January 8 in New York to Paris time.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('Reuse a timezone explicitly supplied in the conversation or evidence',
                             'state the relative offset',
                             'give the destination UTC offset when known',
                             'A scheduling default does not establish the user',
                             'ask for the local date and time, and timezone if unknown',
                             'If an anchor is already supplied, convert it without asking again',
                             'An old timestamp is not a live clock reading',
                             'date-dependent daylight saving and day rollover'):
                    self.assertIn(part, rules)

    def test_test_status_answers_unknown_result_and_uses_supplied_evidence(self):
        for ask in ('Did the Atlas integration checks pass?',
                    'The tests passed at abc123; the current commit is def456. Are we green?'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                self.assertNotIn('say no test run has been seen this turn', rules)
                for part in ('state in first person that the result is unverified',
                             "preserve the user's supplied project name",
                             "latest run's result AND whether its commit matches the current commit",
                             'explain that this establishes whether the run covers current code',
                             'If run evidence is supplied, report its result and tested scope',
                             'Never equate an old passing run with current code passing'):
                    self.assertIn(part, rules)

    def test_empty_decision_records_request_context_without_asserting_its_absence(self):
        for ask in ('What did we decide?', 'WHAT DID WE DECIDE!', '  what did we decide.  '):
            reply = self.say(ask)['content']
            self.assertTrue(reply.startswith('Which decision do you mean?'))
            self.assertIn('topic or earlier messages', reply)
            self.assertIn('recap', reply)
            self.assertNotIn('my notes', reply)
            self.assertEqual(reply.count('?'), 1)
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.bridge.deliver.assert_not_called()
        self.client.create.assert_not_called()

    def test_empty_task_status_identifies_missing_target_before_evidence(self):
        reply = self.say('Is the thing done yet?')['content']
        self.assertTrue(reply.startswith('Which project or task do you mean?'))
        self.assertIn('current result', reply)
        self.assertNotIn('update saved', reply)
        self.assertEqual(reply.count('?'), 1)
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_recorded_decision_is_still_used_without_requesting_it_again(self):
        ledger.record_decision(self.root, 'Keep the launch paused until review.')
        reply = self.say('What did we decide?')['content']
        self.assertIn('Here’s what we decided, from the saved notes:', reply)
        self.assertIn('Keep the launch paused until review.', reply)
        self.assertNotIn('Which decision', reply)
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_handback_evidence_is_still_used_before_empty_fallback(self):
        folder = self.root / 'conductor/handback'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'BOB-STATE.md').write_text(
            '## Decisions\n- Keep the proposal private.\n## Status\n- Atlas: review pending.\n')
        for ask, fact in (('What did we decide?', 'Keep the proposal private.'),
                          ('Is the thing done yet?', 'Atlas: review pending.')):
            reply = self.say(ask)['content']
            self.assertIn('Saved notes (not a live check):', reply)
            self.assertIn(fact, reply)
            self.assertNotIn('Which ', reply)
        self.assertFalse(self.providers.calls)


if __name__ == '__main__':
    unittest.main()
