"""A retained owner failure must reach useful reasoning without invented effects."""
from pathlib import Path
from unittest.mock import patch

from app import Chat
import resource_inventory
import reply_authority
import task_queue
from test_webbob_replyq_1856 import SessionFixture


BRIEF = (Path(__file__).parent / 'fixtures/owner-coordination-1003.txt').read_text()
PROTOCOL = ('`/Users/jeffstory/Documents/bob-overnight-inject/coord/README.md` before any shared work. '
            "Claims and messages are new files only. Never edit someone else's file. One owner per task. "
            'Status is PASS, FAIL, or NOT RUN. This folder is not permission to merge, deploy, spend, or send. '
            "Web Bob's release still follows `BOB-HANDOFF.md`.")


class CoordinationBriefTests(SessionFixture):
    def test_exact_owner_brief_reaches_model_and_preserves_useful_answer_after_reload(self):
        useful = ('The next check is to reconcile the owner, exact source and acceptance evidence '
                  'for each of the three projects. Dot’s reported check does not establish shared '
                  'journal writes or automatic synchronization. I have not read the local records '
                  'in this reply; use their current claims to identify the next unowned task.')
        self.fake.reply_text = useful
        with patch('reply_authority.operational_reply', side_effect=AssertionError('Brief became status')):
            first = self.send(BRIEF)
            self.assertEqual(first['content'], useful)
            self.assertTrue(self.fake.calls)
            self.assertFalse(resource_inventory.question(BRIEF))
            self.assertNotIn('status_observation', first)
            self.assertNotIn('task_id', first)
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            self.assertEqual(self.send('Be more specific')['content'], useful)
        self.assertFalse(task_queue.tasks(self.root))

    def test_observation_is_a_request_not_a_journal_field_or_quoted_instruction(self):
        for prompt in (
            BRIEF,
            PROTOCOL,
            'For the project handoff, record owner, branch, status and evidence before choosing a task.',
            'If we inspect status, record its timestamp first.',
            'If we continue—show our current worker status.',
            'We will decide whether to check status and show our current workers.',
            'Show our current workers only if I approve.',
            'Show our current workers if I approve.',
            'Show our current workers when I approve.',
            'Show our current workers after I approve.',
            'Do not show our current workers. Explain how we should coordinate.',
            'Write a note containing "show our current workers".',
            'Explain the supplied record: status is held, owner is Alice.',
        ):
            with self.subTest(prompt=prompt[:70]):
                self.assertFalse(reply_authority.live_status_question(prompt))
        for prompt in (BRIEF + '\nNow show our current worker status.', 'Status?',
                       'Show our current workers and explain if anything is blocked.',
                       'Show our current worker status before explaining the plan.',
                       'What is the current status after the restart?',
                       'Status with diagnostics', 'Status without internal IDs or raw diagnostics, please',
                       'What is the current Gemini API status?', 'How are the workers doing?'):
            with self.subTest(prompt=prompt[-80:]):
                self.assertTrue(reply_authority.live_status_question(prompt))
        self.assertTrue(resource_inventory.question('What Gemini subscriptions are available?'))
        for prompt in ("What about Gemini's paid quota?", "What about Claude's subscription?"):
            self.assertTrue(resource_inventory.question(prompt))
            self.assertFalse(reply_authority.live_status_question(prompt))
        self.assertFalse(resource_inventory.question('My Dot has started an access check. Record status and evidence.'))

    def test_old_bound_but_misrouted_observation_does_not_capture_correction(self):
        self.send('Status?')
        state = self.chat.get(self.identifier)
        original = next(m for m in state['messages'] if m['role'] == 'user')
        original['content'] = BRIEF
        self.chat.save(state)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.fake.reply_text = 'Start by reconciling each project’s owner and evidence; shared writes remain unverified.'
        with patch('reply_authority.operational_reply', side_effect=AssertionError('Repeating old routing error')):
            answer = self.send('Be more specific')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('status_observation', answer)
        self.assertFalse(task_queue.tasks(self.root))
