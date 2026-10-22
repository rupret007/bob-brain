"""Round-nine prompt contracts and preserved server behavior, without model calls.

These tests establish delivered policy, not sampled model quality or H2H gains.
Private stores and inert transports come from the earlier regression fixtures.
"""
import copy
import unittest

import chat_intent
import test_h2h_round4 as fixtures
from task_dispatch import task_queue


class RoundNineTests(unittest.TestCase):
    setUp = fixtures.RoundFourTests.setUp
    say = fixtures.RoundFourTests.say
    policy = fixtures.RoundFourTests.policy

    def test_simple_plans_keep_checks_internal_and_honor_requested_detail(self):
        rules = self.policy('Organize the files in my receipts folder.')
        for part in ('Treat these requirements as internal checks, not an outline to recite',
                     'For a simple request, omit process headings and closing readiness offers',
                     'Honor requests for detailed plans or comparisons',
                     'Preserve material qualifications'):
            self.assertIn(part, rules)

    def test_cleanup_needs_change_review_not_another_inventory_gate(self):
        rules = self.policy('Tidy my project archive.')
        for part in ('For a simple cleanup, use two compact sentences',
                     'Do not ask for permission merely to inventory',
                     'possible duplicates listed separately',
                     'show proposed moves and any deletions for OK before changing anything',
                     'Do not assume files are disposable from age or extension alone',
                     'claim an inventory was performed without evidence'):
            self.assertIn(part, rules)
        self.assertFalse(task_queue.tasks(self.root))

    def test_latest_search_does_not_inherit_summary_upload_questionnaire(self):
        rules = self.policy('Find the newest rehearsal notes and count the action items.')
        for part in ('Keep latest-file searches to one missing-location question',
                     'do not enumerate upload/paste alternatives or repeat the promised result',
                     'versions and modification dates before reading/counting',
                     'For reading or summarizing a particular document',
                     'ask for an attachment or pasted text',
                     'Use supplied document contents when available',
                     'Never claim a file was found, opened or counted without inspected contents'):
            self.assertIn(part, rules)

    def test_product_shortlists_do_not_require_computer_diagnostics(self):
        rules = self.policy('Suggest affordable wired headphones for a bassist.')
        self.assertNotIn('Ask one workload question covering the user', rules)
        self.assertNotIn('(for audio: DAW, RAM', rules)
        for part in ('For a bounded product recommendation, lead with a small provisional shortlist',
                     'Ask a follow-up only if the missing answer changes the choice',
                     'Do not ask computer-workload questions for unrelated audio gear',
                     'Clarify what the budget includes when components are sold separately',
                     'do not invent current prices, availability or specifications',
                     'isolation alone does not guarantee hearing safety'):
            self.assertIn(part, rules)

    def test_simple_upgrade_decision_retains_evidence_limits_and_workload(self):
        rules = self.policy('Would a newer laptop help with my sample libraries?')
        for part in ('For a simple worth-it upgrade question, give a conditional recommendation',
                     'one short verification caveat and one grouped question',
                     'Only for computer performance or upgrade advice',
                     'DAW, RAM, typical session size and dropouts',
                     'newest model and pricing have not been verified',
                     'do not label a remembered model as newest',
                     'Avoid unconditional performance promises',
                     'Do not turn decision criteria into an architecture lecture'):
            self.assertIn(part, rules)

    def test_short_decline_is_labeled_without_invented_inability_or_reason(self):
        rules = self.policy('Help me decline an invitation to volunteer at the fair.')
        for part in ('Label a proposed social message as a draft outside its body',
                     'Decline the particular invitation as a choice',
                     'do not turn a refusal into a claim of general inability or unavailability',
                     'Retain supplied material terms without assuming they are the reason',
                     'If voice is unspecified, neutral wording can avoid choosing a speaker',
                     'Preserve explicitly quoted or exact wording',
                     'do not add future-contact commitments or invent the reason',
                     'I’ll wait for your OK before sending.'):
            self.assertIn(part, rules)

    def test_focus_advice_is_direct_without_false_calendar_action(self):
        rules = self.policy('How can I fit focus time around my morning appointment?')
        for part in ('For simple advice, use a direct suggestion',
                     'express any proposed check in first-person conditional language',
                     'meeting starts and after it ends, marked Busy',
                     "meeting's end time and other commitments",
                     'Busy signals unavailability; it does not prevent invitations',
                     'do not ask dates for general advice'):
            self.assertIn(part, rules)

    def test_round8_rename_naming_and_conflict_contracts_survive(self):
        rules = self.policy('Give me a few playful titles for a folk album.')
        for part in ('Honor an explicitly supplied date or date source without asking again',
                     'old-to-new filename preview', 'collisions and existing prefixes',
                     'wait for OK before renaming', 'requested number of names',
                     'Check each option for both a recognizable genre cue',
                     'Vary reference sources and joke subjects',
                     'naming guidance applies to invented titles, not factual bios',
                     'conflicts remain unchecked in natural first-person wording once',
                     'Never invent or shorten approval tokens'):
            self.assertIn(part, rules)

    def test_generic_and_send_approvals_keep_distinct_missing_context_replies(self):
        self.assertEqual(self.say('Sounds good, go ahead with that.')['content'],
                         'Which action or draft do you mean? I’m missing the context for that approval.')
        self.assertEqual(self.say('send it')['content'],
                         'Which draft and recipient do you mean? Once identified, '
                         'I’d show the exact message for your OK before sending.')
        self.assertFalse(task_queue.tasks(self.root))
        self.bridge.deliver.assert_not_called()
        self.client.create.assert_not_called()

    def test_deploy_hold_reply_and_scope_remain_grounded(self):
        self.assertEqual(self.say('Hold off on any deploys for Web Bob until I say go.')['content'],
                         "On hold: Web Bob deploys. Say go or resume when you're ready. "
                         'I haven’t checked or paused any external deployment automation.')
        state = self.chat.get(self.cid)['intent_state']
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='deploy Web Bob'),
                         ['Web Bob deploys'])
        self.assertEqual(chat_intent.blocked_scopes(state, ['Web Bob'], action_text='review tests'), [])

    def test_text_draft_keeps_full_token_and_ambiguous_consent_is_inert(self):
        card = self.say('Draft a text to the band: Please bring earplugs.')['text_draft']
        rows = self.chat.get(self.cid)['_texting']['drafts']
        before = copy.deepcopy(rows)
        self.assertRegex(rows[card['id']]['token'], r'^wbtxt-[a-f0-9]{32}$')
        self.assertEqual(card['confirm_message'], 'yes ' + rows[card['id']]['token'])
        self.say('send it')
        self.assertEqual(self.chat.get(self.cid)['_texting']['drafts'], before)
        self.assertIn('Nothing sent', self.say('yes ' + rows[card['id']]['token'][:12])['content'])
        self.bridge.deliver.assert_not_called()


if __name__ == '__main__':
    unittest.main()
