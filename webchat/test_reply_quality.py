"""Deterministic quality and action admission, with offline providers."""
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
import uuid

from app import Chat
from music_notebook import try_music_coach_reply
from reply_quality import check
from task_dispatch import task_queue
from texting_fixture import OfflineProviders


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'chat', self.root, self.providers)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def say(self, text):
        self.chat.submit(self.cid, text, str(uuid.uuid4()))
        end = time.monotonic() + 3
        while self.cid in self.chat.workers and time.monotonic() < end:
            time.sleep(.01)
        return self.chat.history(self.cid)['messages'][-1]['content']

    def test_context_free_fix_requests_actionable_details(self):
        reply = self.say('Fix it.')
        self.assertIn("What's broken?", reply)
        self.assertIn('error', reply)
        self.assertFalse(task_queue.tasks(self.root))

    def test_unbounded_push_proposes_limits_without_dispatch(self):
        reply = self.say('Push everything to the max until midnight.')
        self.assertIn('until midnight', reply)
        self.assertIn('limits', reply)
        self.assertIn('OK', reply)
        self.assertFalse(task_queue.tasks(self.root))

    def test_spreadsheet_stays_pending_until_bound_confirmation(self):
        reply = self.say('Make me a simple spreadsheet to track gig payments: date, venue, amount, paid yes/no.')
        self.assertIn('date, venue, amount, paid yes/no', reply)
        self.assertIn('Reply `yes, start job proposal ' + self.chat.get(self.cid)['pending_job_id'] + '` to create the file.', reply)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertIsNotNone(self.chat.get(self.cid).get('pending_job'))
        self.assertFalse(self.providers.calls)

    def test_capo_explains_mechanism_and_actual_sounding_chord(self):
        reply = self.say("Explain what a capo does like I'm a beginner.")
        self.assertIn('clamp', reply)
        self.assertIn('G shape', reply)
        self.assertIn('sounds like A', reply)
        self.assertNotIn('handback', reply)

    def test_quality_pass_removes_jargon_preserving_negation_and_tokens(self):
        reply = check('Is it done?', 'The lifecycle stage is unverified because no test results were supplied. No receipt. yes wbcal-123')
        self.assertNotIn('lifecycle stage', reply)
        self.assertNotIn('unverified because', reply)
        self.assertIn('No confirmation', reply)
        self.assertIn('yes wbcal-123', reply)
        exact = '`receipt` https://example.test/handback /tmp/handback.txt'
        self.assertEqual(check('Hello', exact), exact)

    def test_model_reply_is_checked_at_delivery(self):
        self.providers.reply = lambda *args: dict(content='The lifecycle stage is pending. No receipt is available.', provider='fixture', attempts=[])
        reply = self.say('Tell me something brief.')
        self.assertNotIn('lifecycle stage', reply)
        self.assertNotIn('receipt', reply)
        self.assertIn('No confirmation', reply)


if __name__ == '__main__':
    unittest.main()
