"""Round-four regressions. Private stores, fixture models, no real transport.

Prompt tests verify the policy reaching the provider, not live model quality.
"""
import copy
import json
import re
import unittest
from unittest.mock import Mock, patch

import chat_intent
from providers import Providers
from task_dispatch import task_queue
from texting import fingerprint
import test_h2h_round3 as fixtures


class RoundFourTests(unittest.TestCase):
    setUp = fixtures.RoundThreeTests.setUp
    say = fixtures.RoundThreeTests.say

    def test_T10_hold_is_draft_only_with_later_exact_approval(self):
        answer = self.say("Draft a text to the band saying practice is moved to Thursday at 7, but don't send it yet.")
        body = answer['text_draft']['body']
        self.assertEqual(body, 'Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.')
        self.assertIn('When ready, reply `yes wbtxt-', answer['content'])
        self.assertNotIn('OK to send', answer['content'])
        row = self.chat.get(self.cid)['_texting']['drafts'][answer['text_draft']['id']]
        self.assertEqual(row['fingerprint'], fingerprint(row))
        self.bridge.deliver.assert_not_called()

    def test_T14_short_approval_preserves_full_token(self):
        answer = self.say('Tell the Pops of Punk group chat we need a setlist by Wednesday.')
        self.assertIn('We need a setlist by Wednesday.', answer['content'])
        self.assertRegex(answer['content'], r'Reply `yes wbtxt-[a-f0-9]{32}` to send\.$')
        self.assertLess(len(answer['content'].split()), 35)
        self.assertEqual(answer['text_draft']['state'], 'pending')
        self.bridge.deliver.assert_not_called()

    def test_T02_sunday_default_is_suggestion_not_schedule(self):
        answer = self.say('Set a reminder every Sunday night to put the trash out.')['content']
        self.assertIn('What time', answer)
        self.assertIn('8 PM Central', answer)
        self.assertIn('pending your OK', answer)
        self.assertFalse(self.chat.reminders.listing())
        self.say('OK')
        self.assertFalse(self.chat.reminders.listing())
        answer = self.say('8pm')['content']
        self.assertRegex(answer, r'yes wbrem-[a-f0-9]{32}')
        self.assertFalse(self.chat.reminders.listing())

    def test_T03_event_reminders_offer_lead_time_generally(self):
        for event in ('band practice', 'choir rehearsal', 'guitar lesson', 'my lesson'):
            with self.subTest(event=event):
                answer = self.say(f'remind me before {event} to restring the strat')['content']
                self.assertIn('When is ' + event + '?', answer)
                self.assertIn('an hour before', answer)
                self.assertIn('wait for your OK', answer)
                self.assertFalse(self.chat.reminders.listing())
        answer = self.say('remind me before band practice to pack my gear')['content']
        self.assertIn('an hour before', answer)
        self.assertNotIn('yes wbrem-', answer)
        rows = json.loads((self.chat.reminders.folder / 'drafts.json').read_text())
        row, = [row for row in rows.values() if row['state'] == 'needs_time']
        self.chat.reminders.handle('yes ' + row['token'], self.cid, 'later', actor='fixture')
        self.assertFalse(self.chat.reminders.listing())

    def test_T04_relative_timer_inactive_with_immediate_alternative(self):
        answer = self.say('Can you remind me in 20 min to check the oven')['content']
        self.assertIn('in 20 minutes', answer)
        self.assertIn("It isn't running yet", answer)
        self.assertIn('phone or oven timer', answer)
        self.assertRegex(answer, r'Reply `yes wbrem-[a-f0-9]{32}` to set\.$')
        self.assertNotRegex(answer, r'\d{1,2}:\d{2}|\b(?:AM|PM)\b')
        self.assertFalse(self.chat.reminders.listing())

    def test_T11_complete_reply_requires_thread_and_recipient_verification(self):
        answer = self.say("Reply to Mike's email and tell him we're in for the gig on the 24th.")['content']
        self.assertNotIn('Subject:', answer)
        self.assertIn('Hi Mike,', answer)
        self.assertIn("We're in for the gig on the 24th.", answer)
        self.assertIn('Please send the load-in time', answer)
        self.assertIn('Thanks,\nJeff', answer)
        self.assertIn('verify the email thread and recipient', answer)
        self.assertTrue(answer.endswith('OK to send once those match?'))
        self.assertIn('still pending', self.say('go ahead')['content'])
        self.bridge.deliver.assert_not_called()
        answer = self.say("Could you reply to Sam's email and tell them the plan looks good.")['content']
        self.assertIn('Hi Sam,', answer)
        self.assertIn('verify the email thread and recipient', answer)
        self.assertNotIn('24th', answer)

    def test_T16_complete_payment_email_requests_unknown_specifics(self):
        answer = self.say('Email my accountant asking if the quarterly estimate is due this month. Show me first.')['content']
        self.assertIn('Subject:', answer)
        self.assertIn('Hi,', answer)
        self.assertIn('Could you let me know if the quarterly estimate is due this month?', answer)
        self.assertIn('confirm the due date and amount', answer)
        self.assertIn('Thanks,\nJeff', answer)
        self.assertTrue(answer.endswith('I’ll wait for your OK before sending.'))
        self.assertNotIn('OK to send', answer)
        self.assertNotRegex(answer, r'\$\d|October|April|January')
        self.assertIn('still pending', self.say('yes')['content'])

    def test_T13_quick_note_is_two_sentences_without_invented_success(self):
        answer = self.say('Write a quick thank-you note to the venue owner for having us last weekend.')['content']
        body = self.chat.get(self.cid)['_personal_action']['body']
        self.assertEqual(body.count('.'), 2)
        self.assertLessEqual(len(body.split()), 35)
        self.assertIn('Thanks for having us last weekend', body)
        self.assertTrue(body.endswith('Jeff'))
        self.assertIn('I’ll wait for your OK before sending.', answer)
        self.assertNotRegex(body, r'crowd|success|smoothly|rock|music')

    def test_T35_unbounded_work_does_not_invent_constraints_or_start(self):
        answer = self.say('Push everything to the max until midnight.')['content']
        for part in ('Which projects', 'limits', 'resource caps', 'until midnight', 'Nothing started', 'Publishing, deployment and spending need your OK'):
            self.assertIn(part, answer)
        self.assertNotIn('existing holds', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_T36_deploy_hold_is_scoped_durable_and_honest(self):
        answer = self.say('Hold off on any deploys for Web Bob until I say go.')['content']
        self.assertIn('On hold: Web Bob deploys.', answer)
        self.assertIn('haven’t checked or paused any external deployment automation', answer)
        state = self.chat.get(self.cid)['intent_state']
        self.assertEqual(state['holds']['Web Bob']['action_scope'], 'deploy')
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='deploy Web Bob'), ['Web Bob deploys'])
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='review Web Bob tests'), [])
        self.assertEqual(chat_intent.blocked_scopes(state, ['WebJam'], action_text='deploy WebJam'), [])
        disk = json.loads((self.chat.state / (self.cid + '.json')).read_text())
        self.assertEqual(disk['intent_state'], state)
        task = dict(conversation_id=self.cid, permission_file=str(self.chat.state / (self.cid + '.json')),
                    project_scopes=['Web Bob'], prompt='deploy Web Bob')
        self.assertIsNotNone(task_queue.permission_block(self.root, task))
        task['prompt'] = 'review Web Bob tests'
        self.assertIsNone(task_queue.permission_block(self.root, task))
        chat_intent.apply_turn(state, 'push Web Bob to the max', 'push')
        self.assertIn('Web Bob', state['holds'])
        chat_intent.apply_turn(state, 'go Web Bob', 'go')
        self.assertFalse(state['holds'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_scoped_hold_cannot_erase_broader_hold(self):
        state = chat_intent.new_state()
        chat_intent.apply_turn(state, 'Hold Web Bob', 'one')
        chat_intent.apply_turn(state, 'Hold deploys for Web Bob', 'two')
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='review tests'), ['Web Bob'])
        state = chat_intent.new_state()
        chat_intent.apply_turn(state, 'Hold all deploys', 'one')
        chat_intent.apply_turn(state, 'push Web Bob to the max', 'two')
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='deploy Web Bob'), ['deploys'])
        state = chat_intent.new_state()
        chat_intent.apply_turn(state, 'Hold Web Bob work and deploys', 'three')
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='review tests'), ['Web Bob'])

    def test_ambiguous_recipient_still_drafts_nothing(self):
        self.bb.chats.return_value.append(dict(guid='SMS;+;other', displayName='THE BAND', participants=[dict(address='other@example.test')]))
        answer = self.say('Draft a text to the band: Hello')
        self.assertIn('Several threads match', answer['content'])
        self.assertNotIn('text_draft', answer)
        self.assertFalse(self.chat.get(self.cid).get('_texting', {}).get('drafts'))
        self.assertNotIn('_personal_action', self.chat.get(self.cid))
        self.bridge.prepare.assert_not_called()
        self.bridge.deliver.assert_not_called()

    def test_text_consent_rejects_bare_embedded_wrong_and_same_request(self):
        answer = self.say('Draft a text to the band: Hello')
        row = self.chat.get(self.cid)['_texting']['drafts'][answer['text_draft']['id']]
        conversation = self.chat.get(self.cid)
        for approval in ('yes', 'go ahead', 'send it', 'please yes ' + row['token'], 'yes wbtxt-' + '0' * 32):
            with self.subTest(approval=approval):
                result = self.chat.texting.confirm(copy.deepcopy(conversation), approval, 'fixture', 'new', Mock())
                self.assertIn('Nothing sent', result)
        result = self.chat.texting.confirm(conversation, 'yes ' + row['token'], 'fixture', row['request_id'], Mock())
        self.assertIn('Nothing sent', result)
        self.bridge.deliver.assert_not_called()

    def test_schedule_requires_exact_token_separate_request_and_respects_hold(self):
        answer = self.say('remind me in 20 minutes to check the oven')['content']
        token = re.search(r'yes (wbrem-[a-f0-9]{32})', answer)[1]
        row = json.loads((self.chat.reminders.folder / 'drafts.json').read_text())[token]
        for approval in ('yes', 'go ahead', 'please yes ' + token, 'yes wbrem-' + '0' * 32):
            self.chat.reminders.handle(approval, self.cid, 'wrong', actor='fixture')
            self.assertFalse(self.chat.reminders.listing())
        self.assertIn('separate message', self.chat.reminders.handle('yes ' + token, self.cid, row['request_id'], actor='fixture'))
        state = chat_intent.new_state()
        chat_intent.apply_turn(state, 'hold everything', 'hold')
        self.assertIn('On hold', self.chat.reminders.handle('yes ' + token, self.cid, 'later', actor='fixture', intent_state=state))
        self.assertFalse(self.chat.reminders.listing())
        self.chat.reminders.handle('yes ' + token, self.cid, 'later', actor='fixture')
        self.assertEqual(len(self.chat.reminders.listing()), 1)
        self.chat.reminders.handle('yes ' + token, self.cid, 'replay', actor='fixture')
        self.assertEqual(len(self.chat.reminders.listing()), 1)

    def test_exact_text_approval_cannot_invent_sent_after_uncertain_handoff(self):
        answer = self.say('Draft a text to the band: Hello')
        token = answer['text_draft']['confirm_message']
        self.bridge.deliver.side_effect = None
        self.bridge.deliver.return_value = 'delivery_unconfirmed'
        reply = self.say(token)['content']
        self.assertIn('unconfirmed', reply.lower())
        self.assertNotRegex(reply, r'(?i)^sent\b|successfully sent')
        self.bridge.deliver.assert_called_once()
        self.say(token)
        self.bridge.deliver.assert_called_once()

    def policy(self, ask):
        provider = Providers(self.root, lambda text: text, runner=Mock(side_effect=AssertionError('No model calls')))
        conversation = dict(id=self.cid, messages=[dict(role='user', content=ask, status='done', request_id='fixture')])
        # Build the real prompt with only isolated fixture state.
        with patch.object(provider, 'snapshot', return_value=[]):
            provider.prompt(conversation, fast=True)
        return ' '.join(provider.current_call.instructions.split())

    def test_T07_calendar_conflict_policy_requests_window_and_no_false_check(self):
        rules = self.policy('Do I have anything conflicting with the show night on the 24th?')
        for part in ('missing month/date and start/end times', 'including travel and preparation time', 'conflicts remain unchecked'):
            self.assertIn(part, rules)

    def test_T08_move_policy_asks_preferences_and_reviewable_change(self):
        rules = self.policy('Move my dentist appointment to next week sometime.')
        for part in ('ask preferred days/times', "other party's availability", 'proposed change for OK before rescheduling', 'Do not imply availability has been checked'):
            self.assertIn(part, rules)

    def test_T17_latest_file_policy_compares_versions_and_counts_only_inspected_contents(self):
        rules = self.policy('Find the latest setlist file and tell me how many songs are on it.')
        for part in ('ask where the files are stored', 'versions and modification dates', 'reading/counting', 'Never claim a file was found, opened or counted without inspected contents'):
            self.assertIn(part, rules)

    def test_T25_upgrade_policy_qualifies_current_claims_and_asks_workload(self):
        rules = self.policy('Is it worth upgrading my computer to the newest one for music production?')
        for part in ('newest model and pricing have not been verified', 'do not label a remembered model as newest', 'DAW, RAM, typical session size and dropouts'):
            self.assertIn(part, rules)

    def test_T26_rules_policy_distinguishes_policy_law_and_exceptions(self):
        rules = self.policy('What are the rules for adopting a dog from a shelter in Illinois, generally?')
        for part in ('distinguish law from organization policy', 'possible shelter policies', 'requirements and exceptions as needing verification', 'official state and local sources', 'do not invent exemption terms'):
            self.assertIn(part, rules)

    def test_T37_test_policy_requires_current_commit_evidence(self):
        rules = self.policy('Did the WebJam tests pass?')
        self.assertIn('state in first person that the result is unverified', rules)
        self.assertIn('whether its commit matches the current commit', rules)
        self.assertIn('Never equate an old passing run with current code passing', rules)

    def test_T38_bio_policy_honors_count_without_fabrication(self):
        rules = self.policy('Write a 2-sentence bio for Rad Dad Band for a venue listing.')
        for part in ('invented genre, repertoire', 'audience response', 'restrained humor only if requested', 'Honor exact sentence counts'):
            self.assertIn(part, rules)
        bio = 'Rad Dad Band packs a dad-sized sense of humor. Grab a seat and brace yourself for the dad jokes.'
        self.providers.reply = Mock(return_value=dict(content=bio, provider='fixture', attempts=[]))
        self.assertEqual(self.say('Write a 2-sentence bio for Rad Dad Band for a venue listing.')['content'], bio)
        self.assertEqual(bio.count('.'), 2)


if __name__ == '__main__':
    unittest.main()
