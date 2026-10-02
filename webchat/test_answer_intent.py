"""Ordinary answers preserve intent; explicit effects still need real execution."""
from test_webbob_replyq_1856 import SessionFixture
from task_dispatch import task_queue, parse_work, task_kind
import threading
import json
import os
from unittest.mock import patch
from providers import Providers, ProviderError


class AnswerIntentTests(SessionFixture):
    def test_instructional_actors_and_state_terms_remain_writing(self):
        examples = (
            "Queued doesn't mean finished.",
            'Queued is not the same as completed.',
            "Assigned doesn’t imply completion.",
            'Use Web Bob for questions and writing; a queued receipt does not mean completion.',
            'Ask Web Bob a question; a queued receipt is not proof of completion.',
            'Welcome to Web Bob—let’s get started!',
            'Web Bob helps you get started with ordinary questions.',
            'I suggest starting with an ordinary question.',
            'I recommend beginning with a short note; use Gemini for writing examples.',
            'Models have separate limits, and queued work has to respect saved project holds.',
        )
        for example in examples:
            with self.subTest(example=example):
                self.fake.reply_text = example
                answer = self.send('Write a practical guide explaining job receipts and how to ask questions.')
                self.assertEqual(answer['status'], 'done')
                self.assertEqual(answer['content'], example)
                self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_instructional_phrasing_preserves_concrete_effect_detection(self):
        descriptions = (
            "Queued doesn't mean finished.",
            'Use Web Bob for questions and writing',
            'Ask Web Bob a question',
            'Welcome to Web Bob—let’s get started!',
            'Web Bob helps you get started with ordinary questions.',
            'I suggest starting with an ordinary question.',
        )
        claims = (
            'I queued your repair.', 'Your repair task was queued.',
            'The parser repair job was dispatched.', 'Codex is now working.',
            'The job was assigned just now.', 'Queued your repair task.',
            'Started your repair task.', 'Job webchat-' + 'b' * 32 + ' is queued.',
        )
        for description in descriptions:
            for claim in claims:
                for boundary in ('; ', ' — ', ' and '):
                    with self.subTest(description=description, claim=claim, boundary=boundary):
                        self.fake.reply_text = description + boundary + claim
                        answer = self.send('Write a practical guide explaining job receipts and how to ask questions.')
                        self.assertNotEqual(answer['content'], self.fake.reply_text)
        for claim in ('Bob started your repair.', 'Gemini queued your repair.',
                      'I started your repair.', 'We will get started on your repair.',
                      'Ask Bob a question; he queued your repair.',
                      'Use Gemini for examples; it has started your repair.',
                      'I suggest starting with a question, considering ' +
                      'the supplied constraints ' * 8 + 'and will queue your repair.',
                      'I will plan carefully, considering ' +
                      'the supplied constraints ' * 5 + 'and use Bob to start your repair.',
                      'Models have separate limits, and queued work has been assigned to Gemini.',
                      'I suggest starting with a question; I assigned your repair to Gemini.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                self.assertNotEqual(self.send('Write a guide explaining job receipts.')['content'], claim)
        self.assertFalse(task_queue.tasks(self.root))

    def test_guide_state_descriptions_are_not_dispatch_receipts(self):
        examples = (
            'A queued receipt confirms that a task was queued, not that it was completed.',
            'A queued status simply indicates a job was assigned, not that it finished.',
            'A queued receipt just means that a job was queued, not that it completed.',
            'Queued work is not finished work.',
            'Scheduled tasks are not necessarily completed tasks.',
            'Queued work is waiting until a worker starts it.',
            'When your task is queued, look for its result before assuming it is finished.',
            'If the repair task is running, wait for its result.',
            'Ask Bob to start a task when you are ready.',
        )
        for example in examples:
            with self.subTest(example=example):
                self.fake.reply_text = example
                reply = self.send('Write a practical guide explaining job receipts.')
                self.assertEqual(reply['status'], 'done')
                self.assertEqual(reply['content'], example)
                self.assertNotIn('task_id', reply)
        self.assertFalse(task_queue.tasks(self.root))

    def test_guide_explanations_do_not_shelter_real_effect_claims(self):
        descriptions = (
            'A queued receipt confirms that a task was queued, not that it completed.',
            'Queued work is not finished work.',
            'When your task is queued, wait for its result.',
            'Ask Bob to start a task when you are ready.',
        )
        claims = (
            'I queued your repair.', 'Your repair task was queued.',
            'Your task is now running.', 'The queued task was assigned just now.',
            'Job webchat-' + 'a' * 32 + ' is queued.',
        )
        for description in descriptions:
            for claim in claims:
                with self.subTest(description=description, claim=claim):
                    self.fake.reply_text = description + ' ' + claim
                    self.assertNotEqual(self.send('Write a guide explaining job receipts.')['content'],
                                        self.fake.reply_text)
        for claim in ('Queued your repair task.', 'Started the repair.',
                      'The queued task was assigned just now.',
                      'I will ask Bob to start your repair.',
                      'I did ask Bob to start your repair.',
                      'Here is how your repair task was queued.',
                      'I confirmed when your repair task was queued.',
                      'Queued jobs are now assigned.',
                      'Queued jobs were assigned to Gemini.',
                      'Scheduled tasks were dispatched.',
                      'A queued receipt confirms your repair task was queued.',
                      'A queued receipt shows that the task was assigned just now.',
                      'Ask Bob to start a task; I queued your repair.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                self.assertNotEqual(self.send('Write a guide explaining job receipts.')['content'], claim)
        self.assertFalse(task_queue.tasks(self.root))

    def test_exact_owner_guide_revision_survives_reload_and_replay(self):
        from app import Chat
        import uuid
        origin = ('Write a 120-word quick-start note for me to use Web Bob. Use only these facts: '
                  'ordinary questions and writing requests can be answered in chat; a queued receipt '
                  'does not prove work finished; saved project holds govern execution; available models '
                  'have separate limits; Auto chooses an existing route. This candidate is being validated, '
                  'so do not claim release readiness or superiority over Grok. Keep it practical and friendly.')
        self.fake.reply_text = 'A starter note.'
        self.send(origin)
        self.send('Actually keep it under 90 words and include one example of a writing request. '
                  'Preserve the facts and qualifications.')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        revision = ('Welcome to Web Bob—let’s get started! Ask questions or request writing in chat, '
                    'such as drafting an email. Queued doesn’t mean finished. Saved project holds govern execution. '
                    'Available models have separate limits; Auto chooses an existing route. '
                    'This candidate is being validated.')
        self.fake.reply_text = revision
        prompt = 'Make that note friendlier while keeping the same word limit, facts, example and qualifications.'
        request_id = str(uuid.uuid4())
        self.chat.submit(self.identifier, prompt, request_id)
        worker = self.chat.workers.get(self.identifier)
        if worker:
            worker['thread'].join(3)
            self.assertFalse(worker['thread'].is_alive())
        delivered = self.chat.get(self.identifier)['messages'][-1]
        self.assertEqual(delivered['status'], 'done')
        self.assertEqual(delivered['content'], revision)
        calls = len(self.fake.calls)
        before = (self.chat.state / (self.identifier + '.json')).read_bytes()
        self.chat.submit(self.identifier, prompt, request_id)
        self.assertEqual(len(self.fake.calls), calls)
        self.assertEqual((self.chat.state / (self.identifier + '.json')).read_bytes(), before)
        self.assertFalse(task_queue.tasks(self.root))

    def test_actual_generic_execution_definition_survives_receipt_guard(self):
        self.fake.reply_text = ('A queued worker is sitting in line waiting its turn — the job is stored and waiting for an available slot. '
                                'Once it picks up a task and starts doing actual work (processing code, generating text, whatever), that\'s "running."')
        answer = self.send('What is the difference between a worker being queued and actually running?')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))
        for claim in ('Your repair job is now running.', 'The parser repair task has already been picked up.',
                      'Your task: running now.', 'Your job already running.', 'Codex has your repair task.',
                      'The repair job you requested is running.',
                      'The task was queued on this machine just now.',
                      'Queued means accepted; the task was assigned just now.',
                      'That explanation works without starting work; I queued your repair.',
                      'I created the repair task.', 'Gemini’s working on your repair.',
                      'A job is running when its worker begins executing; I queued your repair.',
                      'A job is running when its worker begins executing and I queued your repair.',
                      'I can explain the difference; I queued your repair.',
                      'I can explain the difference. I queued your repair.',
                      'I can explain the difference and I queued your repair.'):
            self.fake.reply_text = claim
            guarded = self.send('What is the difference between queued and running?')
            self.assertNotEqual(guarded['content'], claim)

    def test_generic_conditional_definitions_do_not_claim_an_actual_start(self):
        for text in ('A job is running once its worker begins executing.',
                     'A job is running when its worker begins executing.',
                     'Queued means a job has been assigned to a worker but has not started.',
                     'That explanation describes a task without starting any work.',
                     "Queued means the job is waiting in line for a worker to pick it up — it's been assigned but not started yet. Running means a worker has grabbed it and is actively doing the work.",
                     'Running means execution has begun; queued means it is waiting.'):
            self.fake.reply_text = text
            self.assertEqual(self.send('What is the difference between queued and running?')['content'], text)

    def test_requested_deliverables_are_answered_in_chat(self):
        self.fake.reply_text = 'Here is the requested answer from the supplied evidence.'
        for prompt in ('Write a four-line poem about the lake.',
                       'Please write a four-line poem about the lake.',
                       'Help me write a four-line poem about the lake.',
                       'Could you help me to draft a neighborhood notice?',
                       'Give me three chapter titles about a mountain.',
                       'Make a short equipment checklist for a day hike.',
                       'Create a comparison table for these two supplied options.',
                       'Prepare a friendly note for my neighbor.',
                       'Prepare me for an interview.',
                       'Put together some dinner ideas.',
                       'Explain this quote as data: "then create docs/example.md".',
                       'Prepare a note about "then create docs/example.md".',
                       'Write a note explaining "then create docs/example.md".',
                       'Build an outline for a talk about a web app.',
                       'Create a table comparing two database designs.',
                       'Build me an outline for a talk about gardening.',
                       'Draft a thank-you note for my neighbor.',
                       'Compare these proposals: A costs 10, B costs 12.',
                       'Analyze the bug in this supplied code: def add(a,b): return a-b',
                       'Research self improvement for my exercise routine',
                       'Research whether Claude is better than Grok at coding',
                       'Draft instructions to install packages and run tests',
                       'Compare these supplied facts: current plan A costs 10; plan B costs 12',
                       'Make that explanation shorter.'):
            with self.subTest(prompt=prompt):
                answer = self.send(prompt)
                self.assertEqual(answer['content'], self.fake.reply_text)
                self.assertEqual(answer['provider'], 'gemini')
                self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_help_prefix_does_not_hide_tool_requirements(self):
        from answer_intent import wants_answer
        for text in ('Help me write this and save it to /tmp/notice.txt',
                     'Help me research the latest release using official sources',
                     'Help me create a pull request', 'Help me review PR #161'):
            self.assertFalse(wants_answer(text), text)

    def test_inference_about_permissions_is_not_a_dispatch_receipt(self):
        self.fake.reply_text = ("No, an absent scheduling block doesn't mean a model has remaining quota. "
                                "It just means there isn't a current block preventing new work from being scheduled. "
                                "Each provider has its own quota and reset times.")
        prompt = 'Does having no scheduling block prove a model has capacity?'
        self.assertEqual(self.send(prompt)['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))
        self.fake.reply_text += ' I queued your repair.'
        self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        from answer_intent import conceptual
        self.assertFalse(conceptual('Does a queue prove completion? Then run the tests.'))


    def test_explicit_execution_targets_and_worker_choices_remain_tasks(self):
        for prompt in ('Write hello to /tmp/answer-intent-proof.txt',
                       'Review PR #161',
                       'Review services/api.py', 'Fix Web Bob login tests',
                       'Have Gemini research Web Bob browser support',
                       'Codex: write a parser with regression tests',
                       'Create a pull request for the parser fix'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])

    def test_text_deliverable_does_not_hide_explicit_execution_or_worker(self):
        for prompt in ('Create a checklist in /tmp/checklist.md',
                       'Make a checklist in /tmp/checklist.md',
                       'Build an outline in docs/plan.md',
                       'Prepare a note in /tmp/note.md',
                       'Build a checklist web app',
                       'Create a table in the database',
                       'Make a checklist and save it to /tmp/checklist.md',
                       'Create a summary tool for the codebase',
                       'Have Codex make a checklist',
                       'Make a plan then execute it'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])

    def test_explicit_deliverable_destinations_need_coding_capability(self):
        for prompt in ('Make a checklist in /tmp/checklist.md',
                       'Make a checklist in `/tmp/checklist.md`',
                       'Prepare a note in "/tmp/note.md"',
                       "Prepare a note in '/tmp/note.md'",
                       "Prepare a note for Jeff's trip in /tmp/note.md; don't add a date.",
                       'Build an outline in docs/plan.md',
                       'Prepare a note in /tmp/note.md',
                       'Build a checklist web app',
                       'Build a checklist React app',
                       'Make a checklist web app',
                       'Prepare a checklist web app',
                       'Create a SQL table',
                       'Create a database table named customers',
                       'Create a table in the database'):
            with self.subTest(prompt=prompt):
                reply = self.send(prompt)
                row = task_queue.tasks(self.root)[reply['task_id']]
                self.assertEqual(row['kind'], 'coding')
                self.assertNotIn('gemini', task_queue.worker_order(row['kind']))
                self.assertNotIn('minimax', task_queue.worker_order(row['kind']))

    def test_conditional_definitions_preserve_answers_but_not_appended_effects(self):
        prompt = 'What is the difference between a worker being queued and actually running?'
        for definition in ('When a task is queued, it has been submitted but is waiting for a worker.',
                           'If tasks are scheduled, their execution can begin later.',
                           'A job is running once its worker begins executing.'):
            with self.subTest(definition=definition):
                self.fake.reply_text = definition
                self.assertEqual(self.send(prompt)['content'], definition)
        for definition in ('When a task is queued, it waits', 'A job is queued when a slot opens'):
            for claim in (' and your repair task was started.',
                          ', the login repair job was assigned.',
                          '; I started your task.',
                          '. Codex is now working.',
                          '. Job webchat-' + 'a' * 32 + ' is queued.'):
                with self.subTest(definition=definition, claim=claim):
                    self.fake.reply_text = definition + claim
                    self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)

    def test_answer_does_not_use_old_assistant_prose_as_dispatch_permission(self):
        self.fake.reply_text = 'A brief explanation, with no worker needed.'
        self.send('Write a brief explanation of a queue.')
        answer = self.send('Rewrite that explanation in plain language.')
        self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_explanation_of_supplied_job_state_is_not_a_dispatch_claim(self):
        self.fake.reply_text = ('The job is queued. That establishes acceptance, not completion. '
                                'Without a worker claim or output, execution is unproven.')
        answer = self.send('Using only this supplied evidence, explain what is proven: '
                           'the job is queued, no worker claim exists, and no output exists.')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('status_observation', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_supplied_state_paraphrases_and_negative_evidence_survive_delivery(self):
        answer = ('The job is queued. That proves acceptance, not completion. '
                  'No evidence shows the task started; no output proves completion.')
        for state in ('is queued', 'is marked queued', 'was listed as queued', 'has been labelled queued'):
            self.fake.reply_text = answer
            prompt = ('Using only this supplied evidence, explain what is proven and what is not: '
                      f'a job {state}, no worker claim exists, and no output file exists.')
            self.assertEqual(self.send(prompt)['content'], answer)
        for denial in ('The facts do not establish that work has started or finished.',
                       "That doesn't prove the task started.",
                       'There is no evidence that the task started.',
                       'There is no evidence that the task is running.',
                       'There is no evidence that Codex is working on your task.',
                       'The task is not in progress.',
                       'The task has not been picked up.',
                       'The task has not been started.'):
            self.fake.reply_text = denial
            reply = self.send('Someone says that means the work is finished. Are they right? '
                              'Give a direct answer supported by the supplied evidence.')
            self.assertEqual(reply['content'], denial)
        self.assertFalse(task_queue.tasks(self.root))

    def test_practical_guide_preserves_operational_explanations(self):
        self.fake.reply_text = ('Ask ordinary questions or request writing in chat. '
                               'A queued receipt means a job was queued, not that work has started. '
                               'Saved project holds govern execution. Models have separate limits; '
                               'Auto chooses an existing route. This candidate is still being validated.')
        prompt = ('Write a 120-word quick-start note for me to use Web Bob. Use only these facts: '
                  'ordinary questions and writing requests can be answered in chat; a queued receipt '
                  'does not prove work finished; saved project holds govern execution; available models '
                  'have separate limits; Auto chooses an existing route. This candidate is being validated, '
                  'so do not claim release readiness or superiority over Grok. Keep it practical and friendly.')
        answer = self.send(prompt)
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_evidence_reporting_clauses_are_not_owned_task_subjects(self):
        prompt = ('Using only this supplied evidence, explain what is proven and what is not: '
                  'a job is marked queued, no worker claim exists, and no output file exists.')
        # Captured d269f76 provider wording exposed a false dispatch guard.
        # This verifies delivery only; fixture prose is not semantic proof.
        replies = (
            'Based on the supplied evidence, it is proven that the job is currently in a queue, '
            'awaiting processing, and no worker has presently claimed it.',
            'The evidence states that "a job is marked queued, no worker claim exists, and no output file exists."',
            'These conditions indicate the work has not yet started.',
            'That observation describes the job label; it does not establish completion.',
            'This evidence shows the task label, but does not prove execution.',
            'The supplied report shows that tasks were queued.',
            'The queued job is waiting to be assigned to a worker.',
            'The supplied record describes submission to the system and waiting in a queue. Completion is unverified.',
            'No. Completion is not established. Those records describe the task label; '
            'missing evidence alone does not prove that work never happened.',
        )
        for reply in replies:
            with self.subTest(reply=reply):
                self.fake.reply_text = reply
                self.assertEqual(self.send(prompt)['content'], reply)
        self.assertFalse(task_queue.tasks(self.root))

    def test_queue_nouns_do_not_hide_actor_placement_claims(self):
        from dispatch_receipts import claims_dispatch, verbal_effects
        prompt = 'Explain what a queued label proves using only supplied evidence.'
        neutral = 'The supplied record describes submission to the system and waiting in a queue.'
        self.assertFalse(claims_dispatch(neutral, reference=prompt))
        self.assertEqual(len(verbal_effects(neutral)), len(neutral))
        for claim in ('I put it in the queue.', 'The dispatcher moved the task into a queue.',
                      'I added the task to the queue.', 'We sent it to the queue.',
                      'Bob transferred it into the queue.', 'Your task was placed in the queue.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = neutral + ' ' + claim
                self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        for denial in ('I did not put it in the queue.', 'The task was not moved into the queue.'):
            self.assertFalse(claims_dispatch(denial, reference=prompt))
            self.assertTrue(claims_dispatch(denial + ' I put it in the queue.', reference=prompt))
        self.assertFalse(task_queue.tasks(self.root))

    def test_bounded_subjects_still_reject_owned_and_named_effects(self):
        prompt = 'Using only supplied evidence, explain the meaning of a queued label.'
        for subject in ('Your repair job', 'Our parser repair task', 'This task',
                        'That job', 'These jobs', 'Those tasks', 'The parser repair task',
                        'Your queued task', 'The scheduled repair job'):
            for effect in ('was queued', 'has already been assigned', 'got scheduled',
                           'was automatically started', 'was inspected and queued',
                           'will be queued', 'you requested was launched'):
                with self.subTest(subject=subject, effect=effect):
                    claim = subject + ' ' + effect + '.'
                    self.fake.reply_text = 'These conditions do not prove completion; ' + claim
                    self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        for negative in ('The task has not yet been started', 'The task is not currently running'):
            self.fake.reply_text = negative + '; I queued your repair.'
            self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        for claim in ('I queue your task.', 'The system will queue your task.',
                      'Your task is in a queue.', 'Your task was queued.',
                      'The system is queuing your task.'):
            self.fake.reply_text = 'The report mentions the system and waiting in a queue; ' + claim
            self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_targets_require_their_own_action_predicate(self):
        from dispatch_receipts import claims_dispatch
        prompt = ('Write a practical guide using only these facts: a queued receipt does not prove '
                  'work finished; saved project holds govern execution; this candidate is still being validated.')
        neutral = (
            'When reviewing your pending tasks, note that a queued receipt does not prove work finished.',
            'Before reviewing our repair jobs, remember that a scheduled label does not establish completion.',
            'For this task, consider the difference between queued and finished.',
            'Your task descriptions explain what a queued receipt means.',
            'Your task will not be queued.', 'Your task cannot be started.',
        )
        for reply in neutral:
            with self.subTest(reply=reply):
                self.fake.reply_text = reply
                self.assertEqual(self.send(prompt)['content'], reply)
                self.assertTrue(claims_dispatch(reply + ' Your repair task was queued.', reference=prompt))
                self.assertTrue(claims_dispatch(reply + ' I put it in the queue.', reference=prompt))
        for claim in ('Your task, after inspection, was queued.',
                      'Your task, which was queued, is pending.',
                      'Your task which was inspected and queued is pending.',
                      'Your task you requested was launched.',
                      'Your task was inspected carefully and then queued.',
                      'Your task was not queued but was dispatched.',
                      'Your task has not been started, but has been queued.',
                      'Your task will not be queued but was dispatched.',
                      "Your task won't be queued but has been assigned.",
                      'Your task cannot be started but is queued.',
                      'Your task is in our queue.', 'Your task is in your queue.',
                      "Your task is in Jeff's pending queue.",
                      'Your task is ready and will be queued.',
                      'Your task was held and then queued.',
                      '**Your task** will be queued.', 'Your task: queued.'):
            with self.subTest(claim=claim):
                self.assertTrue(claims_dispatch(claim, reference=prompt))
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_followup_uses_adjacent_user_facts_not_old_topic_or_assistant(self):
        self.fake.reply_text = 'The job is queued. Completion is unproven.'
        self.send('Using only supplied evidence: a job is marked queued. Explain what that establishes.')
        followup = 'Give a direct answer supported by the same supplied evidence.'
        self.assertEqual(self.send(followup)['content'], self.fake.reply_text)
        self.send('Write a note about gardening.')
        self.assertNotEqual(self.send(followup)['content'], self.fake.reply_text)
        for corrected in ('Correction to the supplied evidence: the job is not queued.',
                          'Using the same evidence, the job is no longer queued; explain what follows.',
                          'Using the supplied facts, actually the queue record was removed. Explain that.',
                          'Using the same evidence: the job is now running; explain the difference.'):
            self.send('Using only supplied evidence: a job is marked queued. Explain what that establishes.')
            self.assertNotEqual(self.send(corrected)['content'], self.fake.reply_text, corrected)
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_and_negation_cannot_shelter_later_effects(self):
        prefixes = ('The evidence does not prove work started',
                    'That does not prove completion',
                    'Bob has not created a report',
                    'I cannot create a report',
                    'I can explain the difference',
                    "I can offer help; just say go and I'll queue it",
                    'There is no evidence that Codex is working on your task',
                    'No evidence shows the task started',
                    'A queued receipt means a job was queued',
                    'The task has not been started')
        claims = ('I queued your repair.', 'your repair job was assigned.',
                  'the parser repair task was started.', 'Codex is now working.',
                  'the task was queued here just now.', 'job webchat-' + 'e' * 32 + ' is queued.')
        for prefix in prefixes:
            for claim in claims:
                for boundary in ('; ', ', ', ': ', ' — ', ' but ', ' and ', ' even though ', ' although '):
                    self.fake.reply_text = prefix + boundary + claim
                    prompt = 'Write a practical guide explaining queued receipts using only these facts: a job is marked queued.'
                    with self.subTest(prefix=prefix, claim=claim, boundary=boundary):
                        self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_question_cannot_authorize_a_model_action_receipt(self):
        for false_claim in ('I queued the repair for you.', 'Gemini is now working on the repair.',
                            'Your repair job is now queued.', 'The parser task was queued.', 'Queued your repair.',
                            'Queued means accepted; I started the repair.',
                            'The job is webchat-' + 'f' * 32 + '.'):
            self.fake.reply_text = false_claim
            answer = self.send('Using only the supplied facts, explain what a queued job means.')
            self.assertNotEqual(answer['content'], false_claim)
            self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_definition_status_is_an_answer_but_live_status_still_uses_observation(self):
        self.fake.reply_text = 'Queued means accepted. Running requires evidence of execution.'
        answer = self.send('Explain the difference between queued and running status.')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('status_observation', answer)
        live = self.send('Explain the difference between queued and running status and show our current workers.')
        self.assertIn('status_observation', live)

    def test_tool_requirement_in_second_clause_is_preserved(self):
        for prompt, kind in (
                ('Review the tests and run them', 'coding'),
                ('Research the latest Gemini pricing and cite sources', 'research')):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])
                self.assertEqual(task_kind(prompt), kind)
        self.assertIsNone(parse_work('Explain this quote: "and run them"')[0])
        self.assertIsNone(parse_work('Review this supplied note: "latest pricing and cite sources"')[0])


class BudgetAwareRoutingTests(SessionFixture):
    def test_current_voice_answer_prefers_responsive_api_without_extra_reasoning(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        usage = {'gemini':dict(cap_usd=50, committed_usd=46), 'minimax':dict(cap_usd=48, committed_usd=8)}
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(provider.circuit_for(self.identifier), 'snapshot', return_value={}):
            for text in ('Tell me a 150-word story about a compass.',
                         'Tell me a very long story about a sailor. Start right away and keep going for several paragraphs.'):
                conversation['messages'] = [dict(role='user', content=text, status='done',
                    voice_call_id='owned-call', voice_turn_id='owned-turn')]
                self.assertEqual(provider.route_order(conversation)[0], 'gemini')
            provider.prompt(conversation, fast=True)
            self.assertEqual(provider.current_call.thinking_budget, 0)
            # A typed follow-up after a voice call retains ordinary Auto costs.
            conversation['messages'].append(dict(role='user', content=text, status='done'))
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')

    def test_voice_preference_preserves_explicit_choice_health_cap_and_fallback(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user', content='Tell me a long story about a sailor.',
            status='done', voice_call_id='owned-call', voice_turn_id='owned-turn')]
        usage = {'gemini':dict(cap_usd=50, committed_usd=46), 'minimax':dict(cap_usd=48, committed_usd=8)}
        circuit = provider.circuit_for(self.identifier)
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})):
            with patch.object(circuit, 'snapshot', return_value={}) as health:
                conversation['preferred_provider'] = 'minimax'
                self.assertEqual(provider.route_order(conversation)[0], 'minimax')
                conversation['preferred_provider'] = 'auto'
                for state in ('cooldown', 'open', 'busy'):
                    health.return_value = {'gemini':{'state':state}}
                    self.assertEqual(provider.route_order(conversation)[0], 'minimax')
                health.return_value = {}
                usage['gemini']['committed_usd'] = 47.5
                self.assertEqual(provider.route_order(conversation)[0], 'minimax')
                usage['gemini']['committed_usd'] = 46
            attempted = []
            def call(name, *_args):
                attempted.append(name)
                if name == 'gemini':
                    raise ProviderError('temporarily unavailable', kind='network')
                return 'A sailor discovered a hidden island.', None
            with patch.object(provider, 'call', side_effect=call):
                result = provider.reply(conversation, threading.Event(), lambda *_:None)
            self.assertEqual(attempted, ['gemini', 'minimax'])
            self.assertEqual(result['provider'], 'minimax')

    def test_cooldown_is_not_preferred_for_its_lower_cost(self):
        provider = Providers(self.root, self.chat.redact)
        circuit = provider.circuit_for(self.identifier)
        with patch.object(provider, 'spend', return_value={'cap_usd':50,'committed_usd':0}), \
                patch.object(circuit, 'snapshot', return_value={'gemini':{'state':'cooldown'}, 'minimax':{'state':'ready'}}):
            self.assertEqual(provider.available_fast_order({'id':self.identifier})[0], 'minimax')

    def test_auto_uses_healthy_headroom_and_retains_bounded_fallback(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user',content='Draft a friendly welcome note.',status='done')]
        usage = {'gemini':dict(cap_usd=50,committed_usd=46),
                 'minimax':dict(cap_usd=48,committed_usd=8)}
        attempted = []
        def call(name, *_args):
            attempted.append(name)
            if name == 'minimax':
                raise ProviderError('temporarily unavailable', kind='network')
            return 'The supplied figures support the lower-cost option.', None
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(provider, 'call', side_effect=call):
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')
            result = provider.reply(conversation, threading.Event(), lambda *_:None)
        self.assertEqual(attempted, ['minimax','gemini'])
        self.assertEqual(result['provider'], 'gemini')

    def test_precision_prefers_measured_quality_but_still_respects_health_and_cap(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user', content='Compare plans costing 16 and 20.', status='done')]
        usage = {'gemini':dict(cap_usd=50, committed_usd=46), 'minimax':dict(cap_usd=48, committed_usd=8)}
        circuit = provider.circuit_for(self.identifier)
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(circuit, 'snapshot', return_value={}) as health:
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')
            health.return_value = {'gemini':{'state':'cooldown'}}
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')
            health.return_value = {}
            usage['gemini']['committed_usd'] = 47.5
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')

    def test_long_answer_uses_api_quality_route_without_cli_for_length_alone(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user', content='Write a 120-word guide using these facts: ' + 'Supplied detail. ' * 40, status='done')]
        with patch.object(provider, 'available_fast_order', return_value=('gemini','minimax','cursor','codex')):
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')

    def test_capability_roles_use_precision_without_overriding_choice_or_admission(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        usage = {'gemini':dict(cap_usd=50, committed_usd=46), 'minimax':dict(cap_usd=48, committed_usd=8)}
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(provider.circuit_for(self.identifier), 'snapshot', return_value={}):
            for text in ('Can you interface with Grok Bot?', 'I want it to be able to coordinate with Grok.'):
                conversation['messages'] = [dict(role='user', content=text, status='done')]
                self.assertEqual(provider.route_order(conversation)[0], 'gemini')
                provider.prompt(conversation, fast=True)
                self.assertEqual(provider.current_call.thinking_budget, 1024)
            conversation['preferred_provider'] = 'minimax'
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')
            conversation['preferred_provider'] = 'auto'
            usage['gemini']['committed_usd'] = 47.5
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')
            usage['gemini']['committed_usd'] = 46
            conversation['messages'][0]['content'] = 'I want a fictional story about Grok connecting two islands.'
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')

    def test_explicit_choice_and_vision_capability_precede_cost_preference(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user',content='Describe this.',status='done')]
        conversation['preferred_provider'] = 'gemini'
        with patch.object(provider, 'available_fast_order', return_value=('minimax','gemini','cursor','codex')):
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')
            conversation['preferred_provider'] = 'auto'
            conversation['messages'][0]['attachments'] = [dict(kind='image')]
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')


    def test_budget_observation_includes_reservations_and_does_not_trust_stale_board(self):
        provider = Providers(self.root, self.chat.redact)
        ledger = self.root / 'conductor/ledger/gemini.jsonl'
        ledger.parent.mkdir(parents=True)
        locks = self.root / 'conductor/locks'
        locks.mkdir(exist_ok=True)
        (locks/'ledger-gemini.lock').touch()
        data = '\n'.join(json.dumps(row) for row in (
            dict(call_id='settled', cost_usd=40),
            dict(call_id='unsettled', cost_usd=None, reserved_usd=6)))+'\n'
        ledger.write_text(data)
        (self.root/'conductor/lanes.json').write_text(json.dumps({'gemini':{'budget':{'committed_usd':0,'cap_usd':50,'tier':'normal'}}}))
        # Exercise a finite optional ceiling; prepaid default has no known
        # local percentage and must not inherit the stale board's old cap.
        with patch.dict(os.environ, {'BOB_GEMINI_CAP_USD': '50'}):
            observed = provider.spend('gemini')
        self.assertEqual(observed['committed_usd'],46)
        self.assertEqual(observed['reserved_usd'],6)
        self.assertEqual(observed['tier'],'slow')
        self.assertEqual(ledger.read_text(), data)
        ledger.write_text(data+'{torn')
        self.assertFalse(provider.spend('gemini')['quota_known'])
        self.assertEqual(ledger.read_text(), data+'{torn')
