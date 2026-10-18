# Round-5 test changes

Base: `b63c23d`, branch `draft/webbob-h2h-fixes`.

Only obsolete presentation expectations changed. Existing authorization, expiry, recipient binding, fingerprint, replay, hold, and no-effect assertions remain. Full 32-hex tokens remain unchanged; no production approval matcher changed.

## Existing pins (each changed method)

### `webchat/consent_fixture.py::confirm_reply`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Extract the same full exact command from the new backtick footer, still submitting it in a separate request. This is fixture parsing, not production validation.

```diff
--- before

+++ after

@@ -3,3 +3,3 @@

     content = reply['content'] if isinstance(reply, dict) else reply
-    match = re.search(r'reply exactly “(yes (?:wbrem|wblocal)-[0-9a-f]{32})”', content)
+    match = re.search(r'Reply `(yes (?:wbrem|wblocal)-[0-9a-f]{32})`', content)
     test.assertIsNotNone(match, content)
```

### `webchat/remaining_eval.py::approve_reminder`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Extract the same full exact command from the new backtick footer, still submitting it in a separate request. This is fixture parsing, not production validation.

```diff
--- before

+++ after

@@ -2,3 +2,3 @@

     """Exercise the same separate, token-bound consent turn as a chat user."""
-    token = re.search(r'reply exactly “(yes wbrem-[0-9a-f]{32})”', draft['content'])
+    token = re.search(r'Reply `(yes wbrem-[0-9a-f]{32})`', draft['content'])
     assert token is not None, draft
```

### `webchat/test_approval_language.py::assert_blocked`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -19,3 +19,3 @@

                 self.assertEqual(reply['provider'], 'local-tasks')
-                self.assertIn("I haven't created it yet", reply['content'])
+                self.assertIn('Draft file:', reply['content'])
                 with self.actions.locked() as rows:
```

### `webchat/test_approval_language.py::test_empty_detector_result_is_not_effect_authorization`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -15,2 +15,2 @@

                     execute.assert_not_called()
-                    self.assertIn('reply exactly', reply['content'])
+                    self.assertRegex(reply['content'], r'Reply `yes (?:wbrem|wblocal)-[a-f0-9]{32}` to (?:set|create)\.$')
```

### `webchat/test_approval_language.py::test_detector_false_negatives_cannot_authorize_either_effect_lane`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -12,3 +12,3 @@

                     reply = self.submit(prefix + tail)
-                    self.assertIn('reply exactly', reply['content'])
+                    self.assertRegex(reply['content'], r'Reply `yes (?:wbrem|wblocal)-[a-f0-9]{32}` to (?:set|create)\.$')
                     create.assert_not_called()
```

### `webchat/test_approval_language.py::reminder_draft`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -2,3 +2,3 @@

         reply = self.submit('create a reminder for 2am to ' + body)
-        self.assertIn('Nothing was saved', reply['content'])
+        self.assertIn('Draft reminder:', reply['content'])
         return re.search(r'yes (wbrem-[0-9a-f]{32})', reply['content'])[1]
```

### `webchat/test_approval_language.py::test_proposal_filename_still_requires_separate_exact_consent`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -4,3 +4,3 @@

             reply = self.submit('create file ~/Documents/proposal.txt: hello')
-            self.assertIn("I haven't created it yet", reply['content'])
+            self.assertIn('Draft file:', reply['content'])
             execute.assert_not_called()
```

### `webchat/test_calendar_actions.py::test_needs_auth_is_direct_and_never_fabricates_events`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -3,3 +3,3 @@

         reply = self.submit('Create a calendar event Dentist tomorrow at 2pm')['content']
-        self.assertIn('draft for your calendar', reply)
+        self.assertIn('Draft for your calendar', reply)
         self.assertIn('Dentist', reply)
```

### `webchat/test_cap_ledger.py::test_ledger_B10_deferred_and_preview_creation_requires_exact_yes_through_chat`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -17,3 +17,3 @@

                     self.assertEqual(reply['provider'], 'local-tasks')
-                    self.assertIn("I haven't created it yet", reply['content'])
+                    self.assertIn('Draft file:', reply['content'])
                     with chat.local_tasks.locked() as rows:
```

### `webchat/test_cap_ledger.py::test_ledger_B8_draft_and_conditional_creation_requires_exact_yes_through_chat`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -22,3 +22,3 @@

                     self.assertEqual(reply['provider'], 'local-tasks')
-                    self.assertIn("I haven't created it yet", reply['content'])
+                    self.assertIn('Draft file:', reply['content'])
                     with chat.local_tasks.locked() as rows:
```

### `webchat/test_cap_ledger.py::test_ledger_B5_preview_creation_requires_exact_yes_through_chat`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -19,3 +19,3 @@

                     self.assertEqual(reply['provider'], 'local-tasks')
-                    self.assertIn("I haven't created it yet", reply['content'])
+                    self.assertIn('Draft file:', reply['content'])
                     with chat.local_tasks.locked() as rows:
```

### `webchat/test_cap_ledger.py::test_ledger_B1_approval_language_requires_saved_exact_yes`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -23,3 +23,3 @@

                     execute.assert_not_called()
-                    self.assertIn("I haven't created it yet", reply)
+                    self.assertIn('Draft file:', reply)
                     with actions.locked() as rows:
```

### `webchat/test_h2h_round2.py::test_oven_delay_clock_and_separate_durable_consent`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Pin the requested T04 draft-first wording and inactive timer fallback, or the corresponding draft reminder label.

```diff
--- before

+++ after

@@ -2,5 +2,5 @@

         reply = self.say('Can you remind me in 20 min to check the oven')['content']
-        self.assertEqual(reply.splitlines()[0], 'Reminder to check the oven in 20 minutes — OK to set it?')
+        self.assertEqual(reply.splitlines()[0], "Draft reminder: check the oven in 20 minutes. It isn't running yet—use a phone or oven timer if you need it counting now.")
         self.assertNotIn('Proposed reminder', reply)
-        self.assertIn('Not running yet.', reply)
+        self.assertIn("It isn't running yet", reply)
         self.assertFalse(self.chat.reminders.listing())
```

### `webchat/test_h2h_round2.py::test_morning_reminder_synonyms_keep_default_and_require_consent`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -10,3 +10,3 @@

                 self.assertIn('09:00 AM', reply)
-                self.assertIn('OK to set it?', reply)
+                self.assertRegex(reply, r'Reply `yes wbrem-[a-f0-9]{32}` to set\.$')
                 self.assertIn('yes wbrem-', reply)
```

### `webchat/test_h2h_round2.py::test_venue_note_is_full_warm_draft_without_transport_claim`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -5,4 +5,4 @@

         self.assertIn('\nJeff', reply)
-        self.assertTrue(reply.endswith('OK to send to the venue owner?'))
-        self.assertIn('draft', reply)
+        self.assertTrue(reply.endswith('I’ll wait for your OK before sending.'))
+        self.assertIn('Draft for ', reply)
         self.assertNotRegex(reply, r'(?i)transport|auth|config|sent|smoothly')
```

### `webchat/test_h2h_round2.py::test_calendar_available_and_unavailable_keep_details_without_config_prose`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -8,3 +8,3 @@

                 self.assertNotRegex(reply, r'(?i)auth|config|transport|OAuth')
-                self.assertTrue(reply.endswith('OK to add it to your calendar?'))
+                self.assertTrue(reply.endswith('OK to add it to your calendar?' if unavailable else 'to add to your calendar.'))
                 self.client.create.assert_not_called()
@@ -12,3 +12,3 @@

         self.assertIn('Dentist', reply)
-        self.assertIn('pending your OK', reply)
+        self.assertIn('Draft for your calendar:', reply)
         self.assertNotRegex(reply, r'(?i)auth|config|transport')
```

### `webchat/test_h2h_round3.py::test_band_hold_clauses_are_instructions_not_message_content`

Expect a natural greeting and relevant CTA while retaining the supplied fact, time, and recipient; explicit literal text remains unchanged.

```diff
--- before

+++ after

@@ -9,3 +9,3 @@

                 card = reply['text_draft']
-                self.assertEqual(card['body'], 'Practice is moved to Thursday at 7.')
+                self.assertEqual(card['body'], 'Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.')
                 self.assertEqual(card['recipient']['guid'], 'iMessage;+;band')
```

### `webchat/test_h2h_round3.py::test_group_wrappers_resolve_with_exact_token_and_no_send`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Expect a natural greeting and relevant CTA while retaining the supplied fact, time, and recipient; explicit literal text remains unchanged.

```diff
--- before

+++ after

@@ -6,5 +6,5 @@

                 card = reply['text_draft']
-                self.assertEqual(card['body'], 'We need a setlist by Wednesday.')
+                self.assertEqual(card['body'], 'Hey! We need a setlist by Wednesday. Please share your song picks.')
                 self.assertEqual(card['recipient']['guid'], 'iMessage;+;pops')
-                self.assertIn('Not sent. To send, reply: yes wbtxt-', reply['content'])
+                self.assertIn('Reply `yes wbtxt-', reply['content'])
                 self.assertEqual(card['state'], 'pending')
```

### `webchat/test_h2h_round3.py::test_relative_oven_has_no_computed_clock_and_schedules_nothing`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Pin the requested T04 draft-first wording and inactive timer fallback, or the corresponding draft reminder label.

```diff
--- before

+++ after

@@ -2,5 +2,5 @@

         reply = self.say('Can you remind me in 20 min to check the oven')['content']
-        self.assertEqual(reply.splitlines()[0], 'Reminder to check the oven in 20 minutes — OK to set it?')
-        self.assertIn('Not running yet.', reply)
-        self.assertRegex(reply, r'reply exactly “yes wbrem-[a-f0-9]{32}”')
+        self.assertEqual(reply.splitlines()[0], "Draft reminder: check the oven in 20 minutes. It isn't running yet—use a phone or oven timer if you need it counting now.")
+        self.assertIn("It isn't running yet", reply)
+        self.assertRegex(reply, r'Reply `yes wbrem-[a-f0-9]{32}` to set\.')
         self.assertNotRegex(reply, r'\d{1,2}:\d{2}|\b(?:AM|PM)\b')
```

### `webchat/test_h2h_round3.py::test_dentist_spreadsheet_and_research_keep_their_routes`

A usable CSV template now precedes the exact job approval command instead of a status preamble.

```diff
--- before

+++ after

@@ -10,3 +10,3 @@

         self.assertIn('date, venue, amount, paid yes/no', reply['content'])
-        self.assertIn('No job has started', reply['content'])
+        self.assertIn('Spreadsheet template:', reply['content'])
         self.assertFalse(task_queue.tasks(self.root))
```

### `webchat/test_h2h_round4.py::test_T10_hold_is_draft_only_with_later_exact_approval`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Expect a natural greeting and relevant CTA while retaining the supplied fact, time, and recipient; explicit literal text remains unchanged.

```diff
--- before

+++ after

@@ -3,4 +3,4 @@

         body = answer['text_draft']['body']
-        self.assertEqual(body, 'Practice is moved to Thursday at 7.')
-        self.assertIn('Held as a draft. Not sent. When ready, reply: yes wbtxt-', answer['content'])
+        self.assertEqual(body, 'Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.')
+        self.assertIn('When ready, reply `yes wbtxt-', answer['content'])
         self.assertNotIn('OK to send', answer['content'])
```

### `webchat/test_h2h_round4.py::test_T14_short_approval_preserves_full_token`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -3,3 +3,3 @@

         self.assertIn('We need a setlist by Wednesday.', answer['content'])
-        self.assertRegex(answer['content'], r'Not sent\. To send, reply: yes wbtxt-[a-f0-9]{32}$')
+        self.assertRegex(answer['content'], r'Reply `yes wbtxt-[a-f0-9]{32}` to send\.$')
         self.assertLess(len(answer['content'].split()), 35)
```

### `webchat/test_h2h_round4.py::test_T04_relative_timer_inactive_with_immediate_alternative`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Pin the requested T04 draft-first wording and inactive timer fallback, or the corresponding draft reminder label.

```diff
--- before

+++ after

@@ -3,5 +3,5 @@

         self.assertIn('in 20 minutes', answer)
-        self.assertIn('Not running yet', answer)
+        self.assertIn("It isn't running yet", answer)
         self.assertIn('phone or oven timer', answer)
-        self.assertRegex(answer, r'To set it, reply exactly “yes wbrem-[a-f0-9]{32}”$')
+        self.assertRegex(answer, r'Reply `yes wbrem-[a-f0-9]{32}` to set\.$')
         self.assertNotRegex(answer, r'\d{1,2}:\d{2}|\b(?:AM|PM)\b')
```

### `webchat/test_h2h_round4.py::test_T11_complete_reply_requires_thread_and_recipient_verification`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -8,3 +8,3 @@

         self.assertIn('verify the email thread and recipient', answer)
-        self.assertIn('pending your OK', answer)
+        self.assertIn('I’ll wait for your OK before sending.', answer)
         self.assertIn('still pending', self.say('go ahead')['content'])
```

### `webchat/test_h2h_round4.py::test_T13_quick_note_is_two_sentences_without_invented_success`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -7,3 +7,3 @@

         self.assertTrue(body.endswith('Jeff'))
-        self.assertIn('pending your OK', answer)
+        self.assertIn('I’ll wait for your OK before sending.', answer)
         self.assertNotRegex(body, r'crowd|success|smoothly|rock|music')
```

### `webchat/test_h2h_round4.py::test_T07_calendar_conflict_policy_requests_window_and_no_false_check`

The old mandated blanket disclaimer was the bug; require the short trailing unchecked-conflicts/unverified-availability clause instead.

```diff
--- before

+++ after

@@ -2,3 +2,3 @@

         rules = self.policy('Do I have anything conflicting with the show night on the 24th?')
-        for part in ('missing month/date and start/end times', 'including travel and preparation time', 'nothing has been checked or changed'):
+        for part in ('missing month/date and start/end times', 'including travel and preparation time', 'conflicts remain unchecked'):
             self.assertIn(part, rules)
```

### `webchat/test_h2h_round4.py::test_T08_move_policy_asks_preferences_and_reviewable_change`

The old mandated blanket disclaimer was the bug; require the short trailing unchecked-conflicts/unverified-availability clause instead.

```diff
--- before

+++ after

@@ -2,3 +2,3 @@

         rules = self.policy('Move my dentist appointment to next week sometime.')
-        for part in ('ask preferred days/times', "other party's availability", 'proposed change for OK before rescheduling', 'nothing has been checked or changed'):
+        for part in ('ask preferred days/times', "other party's availability", 'proposed change for OK before rescheduling', 'availability is unverified'):
             self.assertIn(part, rules)
```

### `webchat/test_local_tasks.py::draft`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -1,3 +1,3 @@

     def draft(self, text='delete file ~/Documents/note.txt', rid=None):
-        self.assertIn('Local draft; no file changed', self.say(text, rid))
+        self.assertIn('Local draft:', self.say(text, rid))
         return next(r for r in self.rows().values() if r['state'] == 'draft')
```

### `webchat/test_local_tasks.py::test_file_read_list_create_and_terminal_allowlist`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -7,3 +7,3 @@

         self.assertIn('note.txt', self.say('terminal: ls ~/Documents'))
-        self.assertIn("I haven't created it yet", self.say('create file ~/Documents/new.txt: hello\nworld'))
+        self.assertIn('Draft file:', self.say('create file ~/Documents/new.txt: hello\nworld'))
         self.assertFalse((self.home / 'Documents/new.txt').exists())
```

### `webchat/test_personal_drafts.py::test_natural_text_has_concrete_body_and_bound_question`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -3,3 +3,3 @@

         self.assertIn("I'm running 15 minutes late.", reply)
-        self.assertRegex(reply, r'Not sent\. To send, reply: yes wbtxt-[a-f0-9]{32}$')
+        self.assertRegex(reply, r'Reply `yes wbtxt-[a-f0-9]{32}` to send\.$')
         self.assertIn('yes wbtxt-', reply)
```

### `webchat/test_personal_drafts.py::test_missing_channel_keeps_concrete_draft_and_no_job`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -10,3 +10,3 @@

                 self.assertIn(body, reply)
-                self.assertTrue(reply.endswith('I’ll wait for your OK before sending.') if 'email' in ask.lower() else reply.endswith('?'))
+                self.assertTrue(reply.endswith('I’ll wait for your OK before sending.') if not ask.startswith('Book ') else reply.endswith('?'))
                 self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
```

### `webchat/test_personal_drafts.py::test_unresolved_text_transport_keeps_draft`

Expect a natural greeting and relevant CTA while retaining the supplied fact, time, and recipient; explicit literal text remains unchanged. Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -3,4 +3,4 @@

         reply = self.say('Tell the Pops of Punk group chat we need a setlist by Wednesday.')
-        self.assertIn('we need a setlist by Wednesday', reply)
-        self.assertIn('pending', reply)
+        self.assertIn('We need a setlist by Wednesday', reply)
+        self.assertTrue(reply.startswith('Draft for '))
         self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
```

### `webchat/test_personal_drafts.py::test_calendar_natural_language_uses_native_separate_consent`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -4,3 +4,3 @@

         self.assertIn('one-hour', reply)
-        self.assertTrue(reply.endswith('OK to add it to your calendar?'))
+        self.assertTrue(reply.endswith('to add to your calendar.'))
         self.assertIn('yes wbcal-', reply)
```

### `webchat/test_personal_drafts.py::test_missing_calendar_auth_keeps_draft_without_attempting_create`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -5,3 +5,3 @@

         self.assertIn('Dentist', reply)
-        self.assertIn('pending', reply)
+        self.assertTrue(reply.startswith('Draft for '))
         self.assertIn('OK to add it', reply)
```

### `webchat/test_recorded_brief.py::test_short_project_updates_use_saved_facts_and_one_line_per_project`

Plural project requests must cover all five known projects and label missing status, instead of asking which single project; single-task and decision clarifiers stay unchanged.

```diff
--- before

+++ after

@@ -8,3 +8,3 @@

         self.assertIn('WebJam: waiting for review', reply)
-        self.assertEqual(len([line for line in reply.splitlines() if line.startswith('•')]), 2)
+        self.assertEqual(len([line for line in reply.splitlines() if line.startswith('•')]), 5)
         self.assertIn('not a live check', reply)
```

### `webchat/test_recorded_brief.py::test_empty_records_ask_one_question_and_never_guess`

Plural project requests must cover all five known projects and label missing status, instead of asking which single project; single-task and decision clarifiers stay unchanged.

```diff
--- before

+++ after

@@ -3,3 +3,8 @@

             reply = self.say(ask)
-            self.assertEqual(reply.count('?'), 1)
+            if ask.startswith('How are the projects'):
+                self.assertIn('current status isn’t fetched', reply)
+                self.assertIn('one line each', reply)
+                self.assertEqual(reply.count('?'), 0)
+            else:
+                self.assertEqual(reply.count('?'), 1)
             self.assertNotIn('completed', reply)
```

### `webchat/test_reminders.py::test_model_extraction_of_literal_schedule_still_needs_fresh_consent`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact. Pin the requested T04 draft-first wording and inactive timer fallback, or the corresponding draft reminder label.

```diff
--- before

+++ after

@@ -5,4 +5,4 @@

                                      ask, 'chat', 'one', 'owner', chat_intent.new_state())
-        self.assertIn('Reminder: stretching', reply)
-        self.assertIn('OK to set it?', reply)
+        self.assertIn('Draft reminder: stretching', reply)
+        self.assertRegex(reply, r'Reply `yes wbrem-[a-f0-9]{32}` to set\.$')
         self.assertFalse(self.store.listing())
```

### `webchat/test_reply_quality.py::test_spreadsheet_stays_pending_until_bound_confirmation`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -3,3 +3,3 @@

         self.assertIn('date, venue, amount, paid yes/no', reply)
-        self.assertTrue(reply.endswith('OK to create this spreadsheet?'))
+        self.assertIn('Reply `yes, start job proposal ' + self.chat.get(self.cid)['pending_job_id'] + '` to create the file.', reply)
         self.assertFalse(task_queue.tasks(self.root))
```

### `webchat/test_texting_draft_routing.py::test_bare_approvals_use_texting_and_clear_stale_work_in_one_save`

Replace duplicated status/approval prose with the compact draft preview and exact-token approval footer; all effect and authorization assertions stay intact.

```diff
--- before

+++ after

@@ -12,3 +12,3 @@

                 if phrase.startswith('draft'):
-                    self.assertRegex(answer['content'], r'Not sent\. To send, reply: yes wbtxt-[a-f0-9]{32}$')
+                    self.assertRegex(answer['content'], r'Reply `yes wbtxt-[a-f0-9]{32}` to send\.$')
                 else:
```

### `webchat/test_texting_draft_routing.py::test_unavailable_text_replaces_previous_draft_in_one_save`

Use a draft-first heading and one approval/wait line, eliminating repeated pending status; missing-calendar-auth wording still requires review.

```diff
--- before

+++ after

@@ -6,3 +6,3 @@

         self.assertEqual(save.call_count, 1)
-        self.assertIn('pending your OK', answer['content'])
+        self.assertIn('I’ll wait for your OK before sending.', answer['content'])
         self.assertEqual(self.disk()['_personal_action']['kind'], 'text')
```

## New coverage

`webchat/test_h2h_round5.py`: 17 tests covering the exact oven reminder, focus-advice guidance, appointment preference + ready draft + approval guidance, answer-first honesty, natural texts, held drafts, literal/quoted text preservation, specific email subjects, vague-person intent, known-project summaries with partial records, excuse-free decline guidance, CSV template and compact job approval, unchanged exact-token rejection, tamper rejection, reminder separate-request/replay checks, and ambiguous recipients.

Provider tests inspect assembled prompts; no claim of live model quality evaluation is made.
