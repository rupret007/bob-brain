"""Writing content and app effects have independent server-owned contracts."""
import json
from pathlib import Path
import tempfile
import unittest

import reply_contract
from test_webbob_replyq_1856 import SessionFixture


class ArtifactTests(SessionFixture):
    def test_markdown_cannot_fabricate_permission_changes_under_hold(self):
        self.send('Hold all work.')
        for claim in ('The **hold** is **lifted**.', 'The **permission** is **granted**.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                answer = self.send('Explain the next step for the supplied task Q-73. '
                                   'Keep the hold in force; do not execute or send anything.')
                self.assertNotEqual(answer['content'], claim)
                from chat_intent import permission_facts
                self.assertTrue(permission_facts(self.chat.get(self.identifier))['holds'])

    def packet(self, artifact, commentary=''):
        self.fake.reply_text=json.dumps(dict(artifact=artifact,commentary=commentary))

    def test_prefaced_revision_keeps_accepted_draft_across_rejection_but_not_new_topic(self):
        self.packet('We can prepare the bulletin after review.')
        first=self.send('Write a friendly note about preparing a bulletin after review.')
        self.packet('Before I start, please review the draft. Then we can prepare the bulletin.')
        second=self.send('The opening needs work. Start the note with “Before I start” and use two sentences.')
        self.assertTrue(second['artifact']['accepted'])
        self.assertEqual(second['artifact']['source']['message_id'],first['id'])
        self.packet('I queued a task. Receipt: webchat-'+'d'*32)
        rejected=self.send('Make the note shorter.')
        self.assertFalse(rejected.get('artifact'))
        self.chat.close()
        from app import Chat
        self.chat=Chat(self.folder,self.root,self.fake)
        self.packet('Before I start, the draft and recipient list need review. Nothing has been sent.')
        corrected=self.send('One correction: the recipient list also needs review before sending.')
        self.assertTrue(corrected['artifact']['accepted'])
        self.assertEqual(corrected['artifact']['source']['message_id'],second['id'])
        self.fake.reply_text='Four.'
        self.send('Different topic: what is two plus two?')
        self.fake.reply_text='Five.'
        changed=self.send('One correction: add one more.')
        self.assertFalse(changed.get('artifact'))

    def test_writing_reference_never_shelters_an_execution_request(self):
        self.packet('We should review the bulletin.')
        self.send('Write a note about the bulletin.')
        from answer_intent import revises_answer
        self.assertFalse(revises_answer('Start the note with hello. Then deploy the production service.'))

    def test_status_heading_does_not_claim_effect_from_negated_list(self):
        self.send('Help plan a read-only report. Hold execution until scope is chosen.')
        self.fake.reply_text='Task Queue Status: No active tasks, pending assignments, or unhandled effects are in progress. The plan still needs a pinned source revision.'
        answer=self.send('Include source identity and the largest gaps. No changes.')
        self.assertIn('pinned source revision',answer['content'])
        self.fake.reply_text='Task Queue Status: I queued your task.'
        answer=self.send('Include the next planning step.')
        self.assertNotIn('I queued your task.',answer['content'])

    def test_whole_fenced_packet_is_a_draft_but_appended_claim_is_not(self):
        packet=json.dumps(dict(artifact='Before we start, let’s finish the current workflow.',commentary=''))
        self.fake.reply_text='```json\n'+packet+'\n```'
        answer=self.send('Draft a friendly note.')
        self.assertTrue(answer['artifact']['accepted'])
        self.fake.reply_text='```json\n'+packet+'\n```\nI queued your task.'
        rejected=self.send('Write another note.')
        self.assertFalse(rejected.get('artifact'))
        self.assertNotIn('I queued',rejected['content'])

    def test_temporal_first_person_draft_survives_and_revision_retains_identity(self):
        draft='Before we start three integrations, I’d like to finish one useful workflow. We can review the other two afterward.'
        self.packet(draft)
        first=self.send('Draft a friendly note to my teammate explaining this priority.')
        self.assertEqual(first['content'],draft)
        self.assertTrue(first['artifact']['accepted'])
        self.packet('Let’s finish one useful workflow before we start the remaining integrations.')
        second=self.send('Make it shorter and warmer.')
        self.assertEqual(second['artifact']['source']['message_id'],first['id'])
        self.assertNotIn('did not start',second['content'])

    def test_app_claims_appended_in_artifact_or_commentary_do_not_get_exemption(self):
        false = ('Your task is now queued.', 'Queued your job.', 'I queued a review for Codex.',
                 'Claude is now working on it.', 'The message was sent.',
                 'I enabled the workers.', 'I started your task.',
                 'Gemini is handling our chat.', 'Your Web Bob jobs are paused.',
                 'Receipt: webchat-'+'a'*32)
        for claim in false:
            with self.subTest(claim=claim):
                self.packet('Let’s review the plan. '+claim)
                answer=self.send('Draft a brief note to a teammate.')
                self.assertNotIn(claim,answer['content'])
                self.assertFalse(answer.get('artifact'))
        self.packet('Let’s review the plan.','I queued a job for Codex.')
        answer=self.send('Draft a brief note.')
        self.assertFalse(answer.get('artifact'))

    def test_closed_packet_cannot_choose_its_own_purpose_or_append_narration(self):
        for value in ('{"artifact":"Hi","commentary":"","effects":[]}',
                      '{"artifact":"Hi","commentary":""} I queued your task.'):
            self.fake.reply_text=value
            answer=self.send('Write a friendly note.')
            self.assertFalse(answer.get('artifact'))
            self.assertNotIn('I queued',answer['content'])
        self.packet('I queued your task.')
        answer=self.send('What is two plus two?')
        self.assertFalse(answer.get('artifact'))

    def test_topic_change_and_rejected_draft_do_not_become_revision_source(self):
        self.packet('Before we start, let’s decide what success means.')
        first=self.send('Write a friendly note.')
        self.fake.reply_text='Four.'
        self.send('What is two plus two?')
        self.fake.reply_text='It equals four.'
        answer=self.send('Make it clearer.')
        self.assertFalse(answer.get('artifact'))
        contract=self.chat.get(self.identifier)['messages'][-1]['_reply_contract']
        self.assertEqual(contract['kind'],'answer')

    def test_meaning_preserving_revision_keeps_accepted_source_across_reloads(self):
        self.packet('We have five suppliers to review.')
        first=self.send('Write a short note about reviewing five suppliers.')
        self.packet('Review the urgent supplier first, then the other four.')
        second=self.send('Keep the meaning, but acknowledge that one supplier is urgent.')
        self.assertEqual(second['artifact']['source']['message_id'],first['id'])
        self.packet('Review the urgent supplier first, then the other four.')
        third=self.send('Give me the final wording.')
        self.assertEqual(third['artifact']['source']['message_id'],second['id'])


if __name__=='__main__':
    unittest.main()
