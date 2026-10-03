"""Writing content and app effects have independent server-owned contracts."""
import json
from pathlib import Path
import tempfile
import unittest

import reply_contract
from test_webbob_replyq_1856 import SessionFixture


class ArtifactTests(SessionFixture):
    def packet(self, artifact, commentary=''):
        self.fake.reply_text=json.dumps(dict(artifact=artifact,commentary=commentary))

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


if __name__=='__main__':
    unittest.main()
