"""Capability questions must be fast, honest, and free of side effects."""
import copy
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import uuid
from unittest.mock import Mock, patch

from capabilities import QUESTIONS, STACK, grounding, needs_grounding, reply, topic
from test_webchat import Fixture
from texting import Andrea, BlueBubbles, Texting
from texting_fixture import CHATS
from task_dispatch import task_queue


class CapabilityTests(Fixture):
    def ask(self, text, request=None):
        return self.chat.submit(self.identifier, text, request or str(uuid.uuid4()), actor='a' * 64)

    @contextmanager
    def explanation_only(self):
        # Chat may save the explanation itself; no tool execution, credentials,
        # notifications, model calls or action receipts may result from it.
        with ExitStack() as stack:
            for target in (
                'calendar_actions.GoogleCalendar._credentials',
                'calendar_actions.GoogleCalendar.configured',
                'calendar_actions.CalendarActions.handle',
                'calendar_actions.request_json',
                'local_tasks.LocalTasks.handle', 'local_tasks.LocalFiles.execute',
                'local_tasks.search_web', 'reminders.Reminders.create',
                'reminders.notify_macos', 'texting.Andrea.deliver', 'texting.Andrea.call',
                'voice.api_key', 'voice.create_token',
                'urllib.request.OpenerDirector.open', 'socket.socket.connect',
                'subprocess.Popen',
            ):
                stack.enter_context(patch(target, side_effect=AssertionError('Explanation called ' + target)))
            stack.enter_context(patch.object(self.fake, 'reply', side_effect=AssertionError('Model call')))
            yield

    def test_all_supported_questions_are_server_owned_and_idempotent(self):
        for phrases in QUESTIONS.values():
            for question in phrases:
                with self.subTest(question=question):
                    request = str(uuid.uuid4())
                    result = self.ask(question + '?', request)
                    answer = result['messages'][-1]
                    self.assertEqual(answer['provider'], 'capabilities')
                    self.assertEqual(answer['status'], 'done')
                    self.assertFalse(answer['attempts'])
                    self.assertEqual(self.ask(question + '?', request), result)
        self.assertFalse(self.fake.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.get(self.identifier).get('_texting', {}).get('audit'))

    def test_requests_and_quoted_questions_are_not_intercepted(self):
        for text in ('Can you send texts to Alex: On my way', 'Can you remind me to stretch in 10 minutes?',
                     'Can you read files and summarize this PDF?', 'Explain the phrase "can we talk?"',
                     'Remember that my question is can you remember things',
                     'Can you start workers? Fix WebJam.', 'What can you do about this traceback?'):
            self.assertIsNone(topic(text), text)
        result = self.ask('What can you do about this traceback?')
        self.wait()
        self.assertTrue(self.fake.calls)

    def test_git_explanations_answer_the_question_without_execution_or_refusal(self):
        for prompt, expected in (
            ('What does force-push mean?', 'remote branch'),
            ('Explain force push.', 'remote branch'),
            ('Explain gh pr ready.', 'ready for review'),
            ('What does undraft mean?', 'ready for review'),
            ('What does merging a PR mean?', 'target branch'),
        ):
            with self.subTest(prompt=prompt):
                result = self.ask(prompt)['messages'][-1]
                self.assertEqual(result['provider'], 'capabilities')
                self.assertIn(expected, result['content'])
                self.assertNotIn('action_card', result)
                self.assertFalse(result['attempts'])
        self.assertFalse(self.fake.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_explanation_words_do_not_hide_execution_requests(self):
        from app import hard_rule_refusal
        for prompt in ('Explain force-push, then force-push the branch.',
                       'What does undraft mean? Undraft it now.',
                       'Explain gh pr ready and run it.', 'Please merge #158',
                       'Can you force-push?', 'Run gh pr ready'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(topic(prompt))
                self.assertIsNotNone(hard_rule_refusal(prompt))

    def test_capability_answer_revokes_pending_actions_and_memory(self):
        self.ask('remember that this must not be saved')
        conv = self.chat.get(self.identifier)
        self.assertTrue(conv.get('pending_memory'))
        conv.update(pending_job='Fix WebJam', pending_job_id='old',
                    pending_council='Review WebJam', pending_council_id='old')
        self.ask('What can you do?')
        conv = self.chat.get(self.identifier)
        for key in ('pending_memory', 'pending_memory_id', 'pending_job', 'pending_job_id',
                    'pending_council', 'pending_council_id'):
            self.assertNotIn(key, conv)
        result = self.ask('yes, save memory')['messages'][-1]
        self.assertIn('No memory is waiting', result['content'])

    def test_capability_question_cancels_exact_text_approval(self):
        # Use injected boundaries, not even a loopback HTTP server.
        bridge = Mock(spec=Andrea)
        bridge.prepare.side_effect = lambda draft: dict(
            draftId='a' * 64, digest=Andrea.scope_digest(Andrea.scope(draft)),
            actionId='fixture-action', challenge='wbtxt-' + 'b' * 32,
            expiresAt=draft['expires_at'] * 1000)
        bluebubbles = Mock(spec=BlueBubbles)
        bluebubbles.chats.return_value = copy.deepcopy(CHATS)
        self.chat.texting = Texting(bluebubbles, bridge)
        self.chat.texting.instinct.bind_state(self.folder)
        card = self.ask('draft reply to Alex Morgan: Do not send this.')['messages'][-1]['text_draft']
        self.ask('Can you send texts?')
        rejected = self.ask(card['confirm_message'])['messages'][-1]
        self.assertIn('already used, cancelled, or replaced', rejected['content'])
        bridge.deliver.assert_not_called()
        bridge.cancel.assert_called_once()

    def test_capabilities_explain_boundaries_without_exposing_saved_memory(self):
        memory = self.folder / 'memory/profile.md'
        memory.parent.mkdir()
        memory.write_text('Private fixture: copper-puffin-739')
        text = self.ask('Is my memory private?')['messages'][-1]['content']
        self.assertIn('future model context', text)
        self.assertIn('confirmation', text)
        self.assertNotIn('copper-puffin', text)
        self.assertIn('read-only', reply('Can you text Instinct?', self.root))
        self.assertIn('not phone push', reply('Can you set reminders?', self.root))
        self.assertIn('sampled frames', reply('Can you watch videos?', self.root))
        self.assertIn('delivery is unconfirmed', reply('Can you send texts?', self.root))
        self.assertIn('without resending', reply('Can you send texts?', self.root))

    def test_worker_capability_uses_current_solo_and_maintenance_markers(self):
        self.assertIn('can be queued', reply('Can you start workers?', self.root))
        for marker in ('SOLO-WORKER', 'MAINTENANCE'):
            path = self.root / 'conductor' / marker
            path.touch()
            self.assertIn('paused', reply('Can you start workers?', self.root))
            self.assertIn('paused', reply('What can you do?', self.root))
            path.unlink()

    def test_stack_and_missing_feature_answers_are_offline_explanations(self):
        cases = (
            ('What can you do?', ('Google Calendar', 'timers', 'morning routines', 'local files',
                                 'terminal', 'Gmail', 'Google Drive', 'image generation')),
            ('Can you use Google Calendar?', ('authorized Calendar account', 'yes wbcal-', 'No invitations')),
            ('Can you set timers?', ('while Web Bob is running', 'owner opt-in', 'does not prove it fired')),
            ('Can you run morning routines?', ('9am America/Chicago', 'read-only', 'cannot run unattended')),
            ('Can you read local files?', ('owner’s home', 'credentials', 'yes wblocal-', 'not unrestricted')),
            ('Can you run terminal commands?', ('pwd', 'ls PATH', 'cat PATH', 'No shell')),
            ('Can you search the web?', ('successful retrieval', 'not an interactive browser')),
            ('Can you use Gmail?', ('not implemented', 'cannot read your Gmail')),
            ('Can you use Google Drive?', ('not implemented', 'do not grant access')),
            ('Can you use a browser?', ('not implemented', 'Web search', 'does not prove a page')),
            ('Can you generate images?', ('not implemented', 'does not generate')),
            ('Can I send voice memos?', ('not supported', 'Transcription is not guaranteed')),
        )
        with self.explanation_only():
            for question, expected in cases:
                with self.subTest(question=question):
                    answer = self.ask(question)['messages'][-1]
                    self.assertEqual(answer['provider'], 'capabilities')
                    for fragment in expected + ('configured is separate from implemented',
                                                'live availability is not verified', 'performs no action'):
                        self.assertIn(fragment, answer['content'])
                    self.assertFalse(answer['attempts'])
                    for key in ('action_card', 'text_draft', 'calendar_receipt', 'coordination_receipt'):
                        self.assertNotIn(key, answer)
            # Also cover every supported alias under the same fail-closed spies.
            for phrases in QUESTIONS.values():
                for question in phrases:
                    self.assertEqual(self.ask(question)['messages'][-1]['provider'], 'capabilities')
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse((self.folder / 'calendar/receipts.json').exists())
        self.assertFalse((self.folder / 'local-tasks/receipts.json').exists())
        self.assertFalse(self.chat.get(self.identifier).get('_texting', {}).get('audit'))

    def test_voice_limits_match_supported_media_and_call_boundaries(self):
        from chat_media import classify_suffix, MAX_VIDEO_BYTES, MAX_VIDEO_DURATION_S, MAX_VIDEO_FRAMES
        from voice import CALL_SECONDS
        answer = reply("What's the longest voice memo I can send?", self.root)
        for suffix in ('.m4a', '.mp3', '.wav', '.ogg', '.opus'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                classify_suffix(suffix)
        for fragment in (f'{CALL_SECONDS // 60} minutes', f'{MAX_VIDEO_BYTES // (1024 * 1024)} MB',
                         f'{MAX_VIDEO_FRAMES} sampled frames', f'{MAX_VIDEO_DURATION_S} seconds',
                         'first 30 seconds', 'local Whisper', 'cached model', 'budget admission'):
            self.assertIn(fragment, answer)
        self.assertNotIn('unlimited', answer)

    def test_absent_auth_is_unknown_without_reading_credentials(self):
        with self.explanation_only(), patch.dict(os.environ, {}, clear=True):
            for question in ('Is Calendar configured?', 'Can you use Google Calendar?', 'Can we talk?'):
                answer = self.ask(question)['messages'][-1]['content']
                self.assertIn('required setup is not checked', answer)
                self.assertIn('live availability is not verified', answer)
            self.assertIn('without auth, no Calendar action can run',
                          reply('Can you use Google Calendar?', self.root))

    def test_grounding_uses_build_and_resource_observations_without_promoting_them(self):
        import resource_inventory
        observed = self.root / resource_inventory.OBSERVATION
        observed.parent.mkdir(parents=True, exist_ok=True)
        observed.write_text(json.dumps(dict(version=1, resources={
            'gemini': dict(observed_at=1000, authenticated=True, availability='available',
                           secret='fixture-secret-must-not-project')})))
        # A stale candidate/data-root manifest must not replace the loaded code identity.
        (self.root / 'webbob-build.json').write_text(json.dumps(dict(sha='b' * 40, built_at='old')))
        candidate = dict(sha='a' * 40, short_sha='aaaaaaa', built_at='candidate-test-time')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.explanation_only(), patch('build_info.BUILD', candidate):
            facts = grounding(self.root, ['gemini'], self.identifier)
        self.assertEqual(facts['build'], candidate)
        self.assertEqual(facts['live_availability'], 'unverified by this capability explanation')
        gemini = next(r for r in facts['resources']['resources'] if r['name'] == 'gemini')
        self.assertTrue(gemini['observation']['authenticated'])
        self.assertEqual(gemini['observation']['freshness'], 'stale_or_unknown')
        self.assertNotIn('fixture-secret', json.dumps(facts))
        for item in facts['capabilities'][:len(STACK)]:
            self.assertTrue(item['implemented'])
            self.assertEqual(item['configured'], 'unverified')
            self.assertEqual(item['live_verified'], 'unverified')
        for fragment in ('Never promote candidate support', 'time and scope', 'historical success',
                         'absent or expired auth', 'at admission and execution', 'no action receipt'):
            self.assertIn(fragment, facts['status_rules'])
        self.assertEqual(set(facts['missing_capabilities']), {'gmail', 'drive', 'browser', 'image_generation'})
        # Even a recent observed provider login does not verify a Calendar tool
        # or a timer, nor turn candidate code into a deployed feature.
        with self.explanation_only(), patch('resource_inventory.time.time', return_value=1001):
            recent = grounding(self.root, ['gemini'])
        gemini = next(r for r in recent['resources']['resources'] if r['name'] == 'gemini')
        self.assertEqual(gemini['observation']['freshness'], 'recent')
        for item in recent['capabilities'][:len(STACK)]:
            self.assertEqual(item['live_verified'], 'unverified')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_grounding_and_explanations_never_open_protected_auth_files(self):
        original = Path.open

        def safe_open(path, *args, **kwargs):
            if path.name in ('.env', 'keys.env', 'google-calendar.json', 'credentials.json'):
                self.fail('Capability explanation opened protected material')
            return original(path, *args, **kwargs)

        with self.explanation_only(), patch.object(Path, 'open', safe_open), \
                patch.dict(os.environ, {'BOB_GOOGLE_CALENDAR_CREDENTIALS': '/never-read/credentials.json'}):
            self.assertIsNone(reply("What's in my .env file?", self.root))
            self.assertIsNone(reply('Read file ~/.env', self.root))
            self.assertIn('required setup is not checked', reply('Is Calendar configured?', self.root))
            facts = grounding(self.root, [])
        self.assertNotIn('/never-read', json.dumps(facts))

    def test_questions_preserve_holds_and_report_maintenance_without_enabling_work(self):
        self.ask('Hold all work')
        before = copy.deepcopy(self.chat.get(self.identifier)['intent_state'])
        for marker in ('MAINTENANCE', 'SOLO-WORKER'):
            path = self.root / 'conductor' / marker
            path.touch()
            with self.explanation_only():
                for question in ('What can you do?', 'Can you start workers?', 'Can you set timers?',
                                 'Can you use Google Calendar?', 'Can you run morning routines?'):
                    answer = self.ask(question)['messages'][-1]
                    self.assertIn('saved holds', answer['content'])
                    if question in ('What can you do?', 'Can you start workers?'):
                        self.assertIn('paused', answer['content'])
                    self.assertEqual(self.chat.get(self.identifier)['intent_state']['holds'], before['holds'])
                self.assertTrue(grounding(self.root, [])['workers_paused'])
            path.unlink()
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(task_queue.tasks(self.root))

    def test_feature_grounding_does_not_intercept_actions_or_invent_receipts(self):
        for question in ('Can you use Google Calendar without auth?',
                         'Can you use local files and terminal commands?',
                         'Can you handle voice memos like Grok?', 'Is Calendar available now?'):
            with self.subTest(question=question):
                self.assertTrue(needs_grounding(question))
        for action in ('Can you set a timer for 10 minutes?', 'Show my calendar tomorrow',
                       'Can you create a calendar event Dentist tomorrow at 2pm?',
                       'Every morning do read file ~/Documents/notes.txt',
                       'Can you read local files? Then delete ~/Documents/notes.txt',
                       'Send an email to alice@example.test via Gmail',
                       'Go to https://example.test and summarize it',
                       'Generate an image of a sunset', 'Did you send the text to Bob?',
                       'Explain this quote: "Can you use Google Drive?"'):
            with self.subTest(action=action):
                self.assertIsNone(topic(action))
                self.assertIsNone(reply(action, self.root))
