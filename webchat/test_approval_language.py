"""Adversarial consent corpus: verify effects through Chat.submit, offline.

These examples specify behavior, not the detector's vocabulary. Each positive
hedge is exercised against BOTH a schedule and a file create. Quoted content is
deliberately ambiguous: asking again is safer than assuming consent.
"""
from datetime import datetime
from pathlib import Path
import tempfile
import re
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from approval_language import approval_categories, approval_requested
from local_tasks import LocalFiles, LocalTasks
from reminders import ZONE
from task_dispatch import task_queue


POSITIVE = {
    'conditional_approval': (
        'only if I authorize it',
        'provided I agree',
        'after I give the green light',
        'once you hear back from me',
        'after I make up my mind',
        'if I decide this is what I want',
        'unless I explicitly say to proceed',
        'when I have made a decision',
        'on condition that I am happy with it',
        'assuming I am comfortable with the result',
        'subject to my decision',
        'providing that I choose to proceed',
    ),
    'preview_first': (
        'let me see it first',
        'show me a preview',
        'let me look at the result before you proceed',
        'let me check the proposed result first',
        'I would like to see what it looks like first',
        'show me what you would do first',
        'give me a chance to inspect the result',
        'can I take a look first',
        'I want a peek at the result first',
        'show the proposed result to me first',
        'let me carefully examine the result',
        'I need to see the result before anything happens',
    ),
    'draft_only': (
        'draft only',
        'just a draft',
        "don't actually do it",
        'do not make any changes',
        'this is only a proposal',
        'keep this as a rough draft',
        'prepare a provisional version',
        'nothing should actually be changed',
        'without making anything permanent',
        'no changes are to be made',
        'leave the actual action undone',
        'do not carry this out',
    ),
    'wait_for_ok': (
        'wait for my OK',
        'wait for the green light',
        'wait for my go-ahead',
        'wait for my say-so',
        'pause until I get back to you',
        'hold off for now',
        'not yet',
        'await my signal',
        'keep it on hold',
        'put the action on pause',
        'give me time to decide',
        'my nod is needed',
    ),
    'dry_run': (
        'dry run',
        'dry-run only',
        'simulate the operation',
        'simulation mode please',
        'pretend to do it',
        'a rehearsal only',
        'walk me through what would happen',
        'show what would happen without executing anything',
        'hypothetically speaking',
        'just demonstrate the steps',
        'a mock execution',
        'for illustration only',
    ),
    'review_first': (
        'review first',
        'I need to review',
        'for my review',
        'I must scrutinize the result first',
        'let me assess the proposed result',
        'I want to evaluate it first',
        'I need a chance to vet the result',
        'I would like to go over it first',
        'my assessment comes first',
        'I need to look it over',
        'give me an opportunity to audit it',
        'let me double-check the details',
    ),
    'ambiguous_deferral': (
        'after I noodle on it',
        'before you do anything',
        'until I get back',
        'not right now',
        'hold this for later',
        'maybe do this',
        'I am not sure about this',
        'only after the next step',
        '"let me see it first" is the text',
        'the label is "draft only"',
        'the text says "if I choose to proceed"',
        'the title is "dry run"',
    ),
}

# Independently reported constructions and varied syntax, not just substitutions
# in the original seven reproductions. All are exercised without punctuation too.
PREGATE = {
    'ambiguous_deferral': (
        'let me sleep on it',
        'give us a moment',
        'I want another opinion',
        'we should settle this',
        'requires another step',
        'this needs further thought',
        'this depends on the outcome',
        'only a possibility',
    ),
    'conditional_approval': (
        'after getting a thumbs up from me',
        'once the details have been signed off by me',
        'contingent on my acceptance',
        'upon receiving clearance from the owner',
        'after the owner has had a chance to respond',
        'once the outstanding questions are settled',
        'contingent upon a satisfactory outcome',
        'dependent on a decision from the team',
    ),
    'wait_for_ok': (
        'the details must be signed off by me',
        'my acceptance is necessary',
        'a thumbs up from the owner is needed',
        'let me think it over',
        'give us time to consider the consequences',
        'let me reflect on the plan',
        'I need time to mull this over',
        'the owner has to grant clearance',
    ),
    'dry_run': (
        'for discussion purposes only',
        'as an example',
        'just talk me through it',
        'for explanatory purposes',
        'this is an illustrative example',
        'talk us through the process',
        'describe the steps to me',
        'explain the outcome to us',
        'walk me through the process',
        'for educational purposes only',
        'for demonstration purposes',
        'as a thought experiment',
    ),
}
for _category, _phrases in PREGATE.items():
    POSITIVE[_category] += _phrases

# Second independent pre-gate: no punctuation may be needed to withhold intent.
# Include unknown complements so a consent-word list cannot satisfy the suite.
INLINE_RESTRICTIONS = (
    'and run it by me',
    'and run the idea past me',
    'and leave it at the planning stage',
    'and leave it unperformed',
    'as a test run',
    'in theory',
    'for later consideration',
    'and circulate the concept internally',
    'and park the whole thing',
    'and shelve the operation',
    'or put the concept on the back burner',
    'then get another pair of eyes on it',
    'plus a second opinion',
    'also get a second opinion',
    'as a tabletop exercise',
    'as an academic exercise',
    'as a conceptual sketch',
    'as a possible future step',
    'as a feasibility exercise',
    'in principle',
    'in an imaginary setting',
    'in a sandbox',
    'in the realm of possibilities',
    'in the planning stage',
    'for a future conversation',
    'for a second opinion',
    'for eventual deliberation',
    'for later discussion',
    'for a feasibility exercise',
    'with a human in the loop',
    'under human supervision',
    'run it by me',
    'run the idea past me',
    'leave it at the planning stage',
    'leave it unperformed',
    'retain the current state',
    'preserve the current state',
    'later consideration',
    'further deliberation',
    'more thought needed',
    'theoretical exercise',
    'conceptual exercise',
    'speculative exercise',
    'testing the operation',
    'trial execution',
    'unperformed',
    'unapplied',
)
POSITIVE['ambiguous_deferral'] += INLINE_RESTRICTIONS

# Third independent review: consultation order, non-execution modes and
# uncertainty must not depend on a particular verb or a restriction word.
CONSULTATION_RESTRICTIONS = (
    'get my take first',
    'first get back to me',
    'on paper',
    'merely a suggestion',
    'potentially',
    'at the proposal stage',
    'get our perspective first',
    'first collect feedback',
    'get another perspective initially',
    'initially bounce the idea around',
    'my input comes ahead of execution',
    'our response comes next',
    'get my take',
    'get back to me',
    'return the details to us',
    'consult the owner',
    'seek feedback',
    'gather opinions',
    'solicit input',
    'on a provisional basis',
    'on the drawing board',
    'on the table',
    'at the idea stage',
    'at a preliminary stage',
    'at the discussion stage',
    'a proposal',
    'proposed operation',
    'suggested action',
    'a suggestion',
    'a possible step',
    'a possibility',
    'potential action',
    'probably',
    'might proceed',
    'may proceed',
    'potentially feasible',
)
POSITIVE['ambiguous_deferral'] += CONSULTATION_RESTRICTIONS

# Unknown restrictions must be caught by their clause structure even if none
# of their words belongs to a known consent/deferral family.
UNRESOLVED = (
    '; the next move belongs to someone else',
    ', there is another step involved',
    '. The next move belongs to someone else',
    ' — the next move belongs to someone else',
    ' but there is another step involved',
    ' except the next move belongs to someone else',
)

# The latest review plus families of negative action and simulation wording.
EFFECT_RESTRICTIONS = (
    'avoid actually scheduling anything', 'stop short of actually scheduling it',
    'avoid actually saving anything', 'stop short of actually saving it',
    'using practice mode', 'this is a walkthrough',
    'avoid making changes', 'avoiding execution', 'refrain from proceeding',
    'prevent execution', 'suppress the operation', 'skip execution',
    'cease processing', 'halt execution', 'omit the actual operation',
    'abstain from acting', 'a practice session', 'practising the steps',
    'a training exercise', 'a sandbox exercise', 'a tutorial',
    'a tabletop exercise', 'a walkthrough session', 'an imaginary exercise',
)
POSITIVE['ambiguous_deferral'] += EFFECT_RESTRICTIONS

# 24 distinct, clearly authorized bodies, each used for both action types:
# 48 negative requests. Mix command forms as well as content.
AUTHORIZED_BODIES = (
    'stretch', 'drink water', 'walk the dog', 'call Sam', 'water the plants',
    'take a break', 'check the oven', 'stand up', 'feed the cat', 'pack lunch',
    'read a book', 'charge the phone', 'go to bed', 'brush teeth', 'start dinner',
    'bring the umbrella', 'pick up groceries', 'turn the lights off',
    'open the curtains', 'clean the desk', 'wash the dishes', 'take the laundry out',
    'practice piano', 'write a postcard',
)


class ApprovalCategoryTests(unittest.TestCase):
    def test_unknown_secondary_lines_remain_unresolved(self):
        for boundary in ('\n', '\r', '\r\n', '\u0085', '\u2028', '\u2029'):
            for tail in ('glorp the flibbert', 'a zibble stage', 'the quux process'):
                with self.subTest(boundary=repr(boundary), tail=tail):
                    self.assertIn('unresolved_clause', approval_categories(
                        'create a reminder for 2am to stretch' + boundary + tail))

    def test_priority_and_personal_constraints_need_no_known_complement(self):
        for fragment in ('first glorp the flibbert', 'glorp the flibbert first',
                         'initially glorp it', 'my zibble', 'our quux',
                         'glorp it to me', 'glorp it to us', 'on a zibble',
                         'at the quux stage'):
            with self.subTest(fragment=fragment):
                self.assertTrue(approval_requested(
                    'create a reminder for 2am to stretch ' + fragment))

    def test_clock_operands_do_not_resolve_non_time_adjuncts(self):
        for prefix in ('create a reminder for 2am to stretch',
                       'remind me at 2am to stretch',
                       'every morning at 8am remind me to stretch'):
            for tail in ('at the quux stage', 'on a zibble', 'at 2am on paper'):
                with self.subTest(prefix=prefix, tail=tail):
                    self.assertTrue(approval_requested(prefix + ' ' + tail))

    def test_unresolved_grammar_does_not_depend_on_complement_vocabulary(self):
        for connector in ('and', 'or', 'then', 'also', 'plus', 'as', 'in', 'for',
                          'with', 'under', 'by', 'past'):
            for complement in ('glorp the flibbert', 'a zibble stage', 'the quux process'):
                with self.subTest(connector=connector, complement=complement):
                    self.assertIn('unresolved_clause', approval_categories(
                        'create a reminder for 2am to stretch ' + connector + ' ' + complement))

    def test_time_complement_cannot_hide_another_qualifier(self):
        for time in ('for 2am', 'in 10 minutes', 'for tomorrow at 2am'):
            for qualifier in ('as a zibble', 'in the quux stage', 'for a glorp',
                              'and flibbert it'):
                with self.subTest(time=time, qualifier=qualifier):
                    self.assertTrue(approval_requested('set a timer ' + time + ' ' + qualifier))

    def test_time_operands_only_resolve_scheduling_syntax(self):
        for qualifier in ('for 2 days', 'in 10 minutes', 'for tomorrow'):
            with self.subTest(qualifier=qualifier):
                self.assertTrue(approval_requested('create file ~/Documents/result.txt: hello ' + qualifier))


    def test_category_reasons_cover_the_semantic_corpus(self):
        for category, phrases in POSITIVE.items():
            if category == 'ambiguous_deferral':
                continue  # Ambiguity can be detected by any overlapping category.
            for phrase in phrases:
                with self.subTest(category=category, phrase=phrase):
                    self.assertIn(category, approval_categories(phrase))

    def test_spelling_layout_and_content_boundaries_do_not_erase_hedges(self):
        for phrases in POSITIVE.values():
            for phrase in phrases:
                variants = (phrase.upper(), phrase.replace(' ', '\n\t'),
                            phrase.replace('-', '\u2011').replace("'", '\u2019'),
                            'the requested content is "' + phrase + '"; do it now')
                for variant in variants:
                    with self.subTest(variant=variant):
                        self.assertTrue(approval_requested(variant))

    def test_negated_consent_does_not_silently_grant_authority(self):
        for phrase in ('no approval needed', 'do not ask me first',
                       'this is not a dry run', 'without my permission',
                       'never wait for my say-so'):
            with self.subTest(phrase=phrase):
                self.assertTrue(approval_requested(phrase))


class ApprovalIntentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home'
        (self.home / 'Documents').mkdir(parents=True)
        self.now = datetime(2026, 10, 12, 13, tzinfo=ZONE).timestamp()
        # Guard every outbound/effect adapter; real writes are confined to tmp.
        for target in ('urllib.request.OpenerDirector.open', 'subprocess.run',
                       'reminders.notify_macos', 'app.parse_work'):
            guard = patch(target, side_effect=AssertionError('Unexpected effect: ' + target))
            guard.start()
            self.addCleanup(guard.stop)
        clock = patch('time.time', return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        live = patch('app.load_live_ops', return_value={})
        live.start()
        self.addCleanup(live.stop)
        self.providers, self.texting, self.calendar = Mock(), Mock(), Mock()
        self.providers.timeouts = {}
        self.providers.reply.side_effect = AssertionError('Unexpected model call')
        self.texting.handle.return_value = False
        self.texting.public.side_effect = dict
        self.calendar.handle.return_value = None
        self.notifier = Mock()
        self.search = Mock(side_effect=AssertionError('Unexpected search'))
        self.files = LocalFiles(self.home, clock=lambda: self.now)
        self.actions = LocalTasks(self.root / 'local', files=self.files,
                                  search=self.search, clock=lambda: self.now)
        self.chat = Chat(self.root / 'chat', self.root, self.providers,
                         texting=self.texting, calendar=self.calendar,
                         reminder_notifier=self.notifier, local_tasks=self.actions)
        self.chat.reminders.clock = lambda: self.now
        self.addCleanup(self.chat.close)
        self.cid = self.chat.conversation_list()['conversations'][0]['id']

    def submit(self, text):
        reply = self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='owner')['messages'][-1]
        self.providers.reply.assert_not_called()
        self.texting.andrea.deliver.assert_not_called()
        self.notifier.assert_not_called()
        self.search.assert_not_called()
        self.assertFalse(task_queue.tasks(self.root))
        return reply

    def assert_blocked(self, hedge, lane, prefix=None, separator='; '):
        target = self.home / 'Documents/result.txt'
        prefix = prefix or ('create a reminder for 2am to stretch' if lane == 'reminder'
                            else 'create file ~/Documents/result.txt: hello')
        command = prefix + separator + hedge
        with patch.object(self.chat.reminders, 'create', wraps=self.chat.reminders.create) as create, \
                patch.object(self.chat.reminders, 'save', wraps=self.chat.reminders.save) as save, \
                patch.object(self.files, 'execute', wraps=self.files.execute) as execute:
            reply = self.submit(command)
            create.assert_not_called()
            save.assert_not_called()
            execute.assert_not_called()
            self.assertFalse(target.exists())
            self.assertEqual(self.chat.reminders.listing(), [])
            if lane == 'reminder':
                self.assertEqual(reply['provider'], 'reminders')
                self.assertIn('Nothing was saved', reply['content'])
            else:
                self.assertEqual(reply['provider'], 'local-tasks')
                self.assertIn("I haven't created it yet", reply['content'])
                with self.actions.locked() as rows:
                    row, = (r for r in rows.values() if r['state'] == 'draft')
                self.assertIn('yes ' + row['token'], reply['content'])
                self.actions.handle('yes', self.cid, 'bare-yes', {})
                execute.assert_not_called()
        self.assertTrue(approval_requested(command))

    def test_empty_detector_result_is_not_effect_authorization(self):
        # Unknown vocabulary and plain content must both require consent.
        for lane in ('reminder', 'file'):
            for body in ('hello', 'glorp the flibbert', 'zibble quux'):
                with self.subTest(lane=lane, body=body), \
                        patch.object(self.chat.reminders, 'create') as create, \
                        patch.object(self.chat.reminders, 'save') as save, \
                        patch.object(self.files, 'execute') as execute:
                    prefix = ('create a reminder for 2am to ' if lane == 'reminder'
                              else 'create file ~/Documents/result.txt: ')
                    self.assertFalse(approval_requested(prefix + body))
                    reply = self.submit(prefix + body)
                    create.assert_not_called()
                    save.assert_not_called()
                    execute.assert_not_called()
                    self.assertIn('reply exactly', reply['content'])

    def test_detector_false_negatives_cannot_authorize_either_effect_lane(self):
        # The effect boundary must survive *every* detector returning no match.
        for lane in ('reminder', 'file'):
            for tail in EFFECT_RESTRICTIONS[:6]:
                with self.subTest(lane=lane, tail=tail), \
                        patch('approval_language.approval_categories', return_value=frozenset()), \
                        patch.object(self.chat.reminders, 'create') as create, \
                        patch.object(self.chat.reminders, 'save') as save, \
                        patch.object(self.files, 'execute') as execute:
                    prefix = ('create a reminder for 2am to stretch ' if lane == 'reminder'
                              else 'create file ~/Documents/result.txt: hello ')
                    reply = self.submit(prefix + tail)
                    self.assertIn('reply exactly', reply['content'])
                    create.assert_not_called()
                    save.assert_not_called()
                    execute.assert_not_called()
                    self.assertFalse(self.chat.reminders.listing())
                    self.assertFalse((self.home / 'Documents/result.txt').exists())

    def reminder_draft(self, body='stretch'):
        reply = self.submit('create a reminder for 2am to ' + body)
        self.assertIn('Nothing was saved', reply['content'])
        return re.search(r'yes (wbrem-[0-9a-f]{32})', reply['content'])[1]

    def test_reminder_exact_consent_restart_and_replay(self):
        from reminders import Reminders
        token = self.reminder_draft()
        self.assertEqual(self.chat.reminders.listing(), [])
        restored = Reminders(self.chat.reminders.folder.parent, clock=lambda: self.now)
        self.chat.reminders = restored
        with patch.object(restored, 'create', wraps=restored.create) as create:
            for text in ('yes ' + token + ' please', 'yes ' + token.upper(), 'yes wbrem-bad'):
                self.submit(text)
            create.assert_not_called()
            reply = self.submit('yes ' + token)
            self.assertIn('Reminder saved: stretch', reply['content'])
            self.submit('yes ' + token)
            create.assert_called_once()
        self.assertEqual(len(restored.listing()), 1)

    def test_reminder_draft_binding_expiry_replacement_and_cancel(self):
        token = self.reminder_draft()
        store = self.chat.reminders
        with patch.object(store, 'create', wraps=store.create) as create:
            for cid, actor in (('another-chat', 'owner'), (self.cid, 'someone-else')):
                store.handle('yes ' + token, cid, 'different-request', actor=actor)
            with store.draft_lock() as drafts:
                rid = drafts[token]['request_id']
            store.handle('yes ' + token, self.cid, rid, actor='owner')
            create.assert_not_called()
            replacement = self.reminder_draft('drink water')
            self.submit('yes ' + token)
            self.submit('cancel ' + replacement)
            self.submit('yes ' + replacement)
            expired = self.reminder_draft()
            self.now += 3601
            self.submit('yes ' + expired)
            create.assert_not_called()

    def test_reminder_confirmation_checks_saved_hold_and_original_project(self):
        token = self.reminder_draft('review WebBob')
        self.submit('Hold WebBob')
        reply = self.submit('yes ' + token)
        self.assertIn('On hold:', reply['content'])
        self.assertFalse(self.chat.reminders.listing())
        with patch('app.parse_work', return_value=(None, None)):
            self.submit('resume WebBob')
        self.assertIn('Reminder saved:', self.submit('yes ' + token)['content'])

    def test_reminder_draft_and_consumption_storage_failures_never_create(self):
        with patch.object(self.chat.reminders, 'save_drafts', side_effect=OSError('disk full')), \
                patch.object(self.chat.reminders, 'create') as create:
            self.submit('create a reminder for 2am to stretch')
            create.assert_not_called()
        token = self.reminder_draft()
        with patch.object(self.chat.reminders, 'save_drafts', side_effect=OSError('disk full')), \
                patch.object(self.chat.reminders, 'create') as create:
            self.submit('yes ' + token)
            create.assert_not_called()

    def test_unconfirmed_reminder_never_delivers_or_retries_after_create_error(self):
        token = self.reminder_draft()
        with patch.object(self.chat.reminders, 'create', side_effect=OSError('unknown outcome')) as create:
            self.assertNotIn('Reminder saved:', self.submit('yes ' + token)['content'])
            self.submit('yes ' + token)
            create.assert_called_once()
        self.now += 86400
        self.chat.deliver_reminders()
        self.assertFalse(self.chat.reminders.listing())
        self.notifier.assert_not_called()

    def test_reminder_draft_due_time_cannot_roll_forward_on_late_consent(self):
        draft = self.submit('set a timer for 1 second')
        token = re.search(r'yes (wbrem-[0-9a-f]{32})', draft['content'])[1]
        self.now += 2
        self.assertIn('expired', self.submit('yes ' + token)['content'])
        self.assertFalse(self.chat.reminders.listing())

    def test_concurrent_reminder_confirmations_create_once(self):
        from concurrent.futures import ThreadPoolExecutor
        token = self.reminder_draft()
        store = self.chat.reminders
        with patch.object(store, 'create', wraps=store.create) as create:
            with ThreadPoolExecutor(4) as pool:
                replies = list(pool.map(lambda i: store.handle('yes ' + token, self.cid,
                                    'confirm-' + str(i), actor='owner'), range(8)))
            create.assert_called_once()
        self.assertTrue(all('Reminder saved:' in reply for reply in replies))
        self.assertEqual(len(store.listing()), 1)

    def test_routine_confirmation_revalidates_path_without_scheduling(self):
        target = self.home / 'Documents/note.txt'
        target.write_text('plain')
        draft = self.submit('every morning do read file ~/Documents/note.txt')
        token = re.search(r'yes (wbrem-[0-9a-f]{32})', draft['content'])[1]
        target.unlink()
        reply = self.submit('yes ' + token)
        self.assertIn('path is unavailable', reply['content'])
        self.assertFalse(self.chat.reminders.listing())

    def test_corpus_size_and_unique_examples(self):
        positives = [text for phrases in POSITIVE.values() for text in phrases]
        self.assertGreaterEqual(len(set(positives)), 100)
        self.assertEqual(len(positives), len(set(positives)))
        self.assertGreaterEqual(len(set(AUTHORIZED_BODIES)) * 2, 40)

    def test_proposal_filename_still_requires_separate_exact_consent(self):
        target = self.home / 'Documents/proposal.txt'
        with patch.object(self.files, 'execute', wraps=self.files.execute) as execute:
            reply = self.submit('create file ~/Documents/proposal.txt: hello')
            self.assertIn("I haven't created it yet", reply['content'])
            execute.assert_not_called()
            self.assertFalse(target.exists())
            with self.actions.locked() as rows:
                row, = rows.values()
            self.actions.handle('yes', self.cid, 'bare-yes', {})
            execute.assert_not_called()
            self.assertIn('File created:', self.submit('yes ' + row['token'])['content'])
            self.assertEqual(target.read_text(), 'hello')
            execute.assert_called_once()
            self.submit('yes ' + row['token'])
            execute.assert_called_once()

    def test_shared_hedges_do_not_depend_on_the_following_verb(self):
        for connector in ('after I', 'before you', 'until I', 'once you', 'when I', 'only after I'):
            for completion in ('sleep on it', 'noodle on it', 'return from lunch',
                               'finish pondering', 'talk to Sam', 'have more information',
                               'take a second look', 'reach a conclusion'):
                with self.subTest(connector=connector, completion=completion):
                    self.assertTrue(approval_requested(connector + ' ' + completion))


def positive_case(hedge, lane, prefix=None, separator='; '):
    def test(self):
        self.assert_blocked(hedge, lane, prefix, separator)
    return test


def authorized_case(body, lane, index):
    def test(self):
        if lane == 'reminder':
            prefix = ('create a reminder for 2am to ', 'please set an alarm for 2am to ',
                      'could you schedule a reminder for 2am to ', 'remind me at 2am to ')[index % 4]
            command = prefix + body
            self.assertFalse(approval_requested(command))
            reply = self.submit(command)
            self.assertEqual(self.chat.reminders.listing(), [])
            token = re.search(r'yes (wbrem-[0-9a-f]{32})', reply['content'])[1]
            reply = self.submit('yes ' + token)
            self.assertIn('Reminder saved:', reply['content'])
            row, = self.chat.reminders.listing()
            self.assertEqual((row['body'], row['state']), (body, 'pending'))
            self.assertEqual(row['due_at'], datetime(2026, 10, 13, 2, tzinfo=ZONE).timestamp())
        else:
            prefix = ('create file ', 'please create a file ', 'could you create file ',
                      'create a local file ')[index % 4]
            command = prefix + '~/Documents/result.txt: ' + body
            self.assertFalse(approval_requested(command))
            reply = self.submit(command)
            self.assertFalse((self.home / 'Documents/result.txt').exists())
            token = re.search(r'yes (wblocal-[0-9a-f]{32})', reply['content'])[1]
            reply = self.submit('yes ' + token)
            self.assertIn('File created:', reply['content'])
            self.assertEqual((self.home / 'Documents/result.txt').read_text(), body)
    return test


# Separate unittest cases keep every paraphrase visible in failing-first output.
for _category, _phrases in POSITIVE.items():
    for _index, _hedge in enumerate(_phrases):
        for _lane in ('reminder', 'file'):
            setattr(ApprovalIntentTests, f'test_block_{_category}_{_index:02d}_{_lane}',
                    positive_case(_hedge, _lane))
    for _index, _prefix in enumerate(('set a timer for 10 minutes to stretch',
                                      'remind me every 2 hours to stretch',
                                      'every morning remind me to stretch',
                                      'every morning do read file ~/Documents/result.txt')):
        setattr(ApprovalIntentTests, f'test_schedule_form_{_category}_{_index:02d}',
                positive_case(_phrases[0], 'reminder', _prefix))
for _index, _body in enumerate(AUTHORIZED_BODIES):
    for _lane in ('reminder', 'file'):
        setattr(ApprovalIntentTests, f'test_authorized_{_index:02d}_{_lane}',
                authorized_case(_body, _lane, _index))

for _category, _phrases in PREGATE.items():
    for _index, _hedge in enumerate(_phrases):
        for _lane in ('reminder', 'file'):
            for _layout, _separator in (('inline', ' '), ('newline', '\n')):
                setattr(ApprovalIntentTests,
                        f'test_pregate_{_category}_{_index:02d}_{_lane}_{_layout}',
                        positive_case(_hedge, _lane, separator=_separator))
for _index, _clause in enumerate(UNRESOLVED):
    for _lane in ('reminder', 'file'):
        setattr(ApprovalIntentTests, f'test_unresolved_clause_{_index:02d}_{_lane}',
                positive_case(_clause, _lane, separator=''))

# Exercise every hedge inline/newline/quoted through both real routing lanes.
# Existing corpus cases also get inline coverage, not just punctuation coverage.
for _category, _phrases in POSITIVE.items():
    for _index, _hedge in enumerate(_phrases):
        for _lane in ('reminder', 'file'):
            setattr(ApprovalIntentTests, f'test_inline_{_category}_{_index:02d}_{_lane}',
                    positive_case(_hedge, _lane, separator=' '))
for _index, _hedge in enumerate(INLINE_RESTRICTIONS):
    for _lane in ('reminder', 'file'):
        for _layout, _value in (('newline', _hedge.replace(' ', '\n')),
                                ('quoted', '"' + _hedge + '"')):
            setattr(ApprovalIntentTests, f'test_repair_{_index:02d}_{_lane}_{_layout}',
                    positive_case(_value, _lane, separator=' '))

for _index, _hedge in enumerate(CONSULTATION_RESTRICTIONS):
    for _lane in ('reminder', 'file'):
        for _layout, _value in (('newline', _hedge), ('quoted', '"' + _hedge + '"')):
            setattr(ApprovalIntentTests, f'test_consultation_{_index:02d}_{_lane}_{_layout}',
                    positive_case(_value, _lane, separator='\n' if _layout == 'newline' else ' '))
for _index, _tail in enumerate(('glorp the flibbert', 'a zibble stage', 'the quux process')):
    for _lane in ('reminder', 'file'):
        setattr(ApprovalIntentTests, f'test_unknown_line_{_index:02d}_{_lane}',
                positive_case(_tail, _lane, separator='\n'))
