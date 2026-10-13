"""Status and decision questions use recorded facts rather than model guesses."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid

from app import Chat
import ledger
from texting_fixture import OfflineProviders


class RecordedBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'chat', self.root, self.providers)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def say(self, text):
        return self.chat.submit(self.cid, text, str(uuid.uuid4()))['messages'][-1]['content']

    def test_short_project_updates_use_saved_facts_and_one_line_per_project(self):
        state = ledger.default_state()
        state['jobs'] = [dict(job_id='one', plain_now='Web Bob: draft tests passed'),
                         dict(job_id='two', plain_now='WebJam: waiting for review')]
        ledger.save_state(self.root, state)
        reply = self.say('How are the projects going? Short version')
        self.assertIn('Web Bob: draft tests passed', reply)
        self.assertIn('WebJam: waiting for review', reply)
        self.assertEqual(len([line for line in reply.splitlines() if line.startswith('•')]), 2)
        self.assertIn('not a live check', reply)
        self.assertFalse(self.providers.calls)
        self.assertIn('draft tests passed', self.say('Is the thing done yet'))

    def test_queue_status_is_recorded_completion_not_live_deployment(self):
        folder = self.root / 'conductor/state'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'queue.jsonl').write_text(json.dumps(dict(id='one', status='succeeded',
                prompt='Fix Web Bob login', projects=['Web Bob'], updated_at=1)) + '\n')
        reply = self.say('Is the thing done yet')
        self.assertIn('Web Bob: work completed', reply)
        self.assertIn('I haven’t confirmed deployment', reply)
        self.assertIn('not a live check', reply)
        self.assertFalse(self.providers.calls)

    def test_decisions_are_quoted_from_ledger_without_new_authorization(self):
        ledger.record_decision(self.root, 'Keep Web Bob deploys on hold.')
        reply = self.say('What did we decide?')
        self.assertIn('Keep Web Bob deploys on hold.', reply)
        self.assertIn('Here’s what we decided, from the saved notes:', reply)
        self.assertFalse(self.providers.calls)

    def test_empty_records_ask_one_question_and_never_guess(self):
        for ask in ('What did we decide?', 'Is the thing done yet', 'How are the projects going? Short version'):
            reply = self.say(ask)
            if ask.startswith('How are the projects'):
                self.assertIn('current status isn’t fetched', reply)
                self.assertIn('one line each', reply)
                self.assertEqual(reply.count('?'), 0)
            else:
                self.assertEqual(reply.count('?'), 1)
            self.assertNotIn('completed', reply)
        self.assertFalse(self.providers.calls)

    def test_existing_saved_notes_are_used_when_ledger_empty(self):
        folder = self.root / 'conductor/handback'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'BOB-STATE.md').write_text('## Projects\n- Web Bob: review pending\n## Decisions\n- Keep drafts private\n')
        self.assertIn('Web Bob: review pending', self.say('Is the thing done yet'))
        self.assertIn('Keep drafts private', self.say('What did we decide?'))


if __name__ == '__main__':
    unittest.main()
