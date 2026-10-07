"""Source conditions survive final delivery without turning into live authority."""
import copy
import json
import unittest
from unittest.mock import patch

import decision_context as dc
from test_webbob_replyq_1856 import SessionFixture
import task_queue

ORIGIN=('Planning example only: our hosted model has stopped because its credit is exhausted. '
        'We have an authenticated subscription chat route and a separate subscription route for read-only reports. '
        'Nobody has checked their remaining allowance, optional overage settings, or answer quality for this task. '
        'What is a sensible way forward? Do not execute anything.')
INPUTS=('The report route receives supplied text and has no file-reading tools. '
        'Proposal Alder is available, but proposal Birch is on an inaccessible drive. '
        'What useful preparation can we do now?')


def add(c,text,role='user'):
    i=str(len(c['messages']))
    c['messages'].append(dict(id=i,request_id=i,role=role,content=text,status='done'))


class ProjectionTests(unittest.TestCase):
    def scenario(self):
        c={'messages':[]}; add(c,ORIGIN); add(c,INPUTS)
        return c

    def test_conditions_keep_subject_provenance_and_separate_unknowns(self):
        c=self.scenario();p=dc.project(c,lambda v:v)
        facts={r['key']:r for r in p['facts']}
        self.assertIn('funding.hosted model',facts)
        self.assertIn('hosted model has stopped because its credit is exhausted',facts['funding.hosted model']['statement'])
        for name in ('allowance','overage','quality'):
            self.assertIn('checks.chat route.'+name,facts)
            self.assertIn('checks.report route.'+name,facts)
        self.assertIn('input.proposal birch',facts)
        for r in p['facts']:
            m=c['messages'][int(r['source']['message_id'])]
            self.assertEqual(dc.digest(m['content']),r['source']['source_sha256'])

    def test_matching_corrections_replace_only_their_condition(self):
        c=self.scenario()
        add(c,'Correction: the hosted model credit is restored. Proposal Birch is now available. What is the next step?')
        p=dc.project(c,lambda v:v);text=' '.join(r['statement'] for r in p['facts'])
        self.assertNotIn('exhausted',text)
        self.assertNotIn('inaccessible',text)
        self.assertIn('restored',text)
        self.assertIn('now available',text)
        self.assertIn('Answer quality',text)
        self.assertEqual(len(p['superseded']),2)

    def test_one_input_correction_does_not_restore_another(self):
        c=self.scenario()
        add(c,'Proposal Cedar is unavailable. What can we prepare?')
        add(c,'Correction: proposal Birch is available. What is the next step?')
        p=dc.project(c,lambda v:v);text=' '.join(r['statement'] for r in p['facts'])
        self.assertIn('Cedar is unavailable',text)
        self.assertIn('Birch is available',text)
        self.assertNotIn('Birch is on an inaccessible',text)

    def test_scenario_followup_and_local_check_correction_preserve_other_subjects(self):
        c=self.scenario();origin=dc.project(c,lambda v:v)['origin']
        add(c,'In this scenario, what should the report route do next?')
        p=dc.project(c,lambda v:v)
        self.assertEqual(p['origin'],origin)
        self.assertIn('input.proposal birch',{r['key'] for r in p['facts']})
        add(c,'Correction: in this scenario the chat route answer quality is now verified. What is the next step?')
        p=dc.project(c,lambda v:v);facts={r['key']:r for r in p['facts']}
        self.assertIn('not checked',facts['checks.report route.quality']['statement'])
        self.assertIn('now verified',facts['checks.chat route.quality']['statement'])
        self.assertIn('funding.hosted model',facts)
        add(c,'Correction: Proposal Birch is available, but disregard the earlier funding statement. What is the next step?')
        p=dc.project(c,lambda v:v)
        self.assertNotIn('funding.hosted model',{r['key'] for r in p['facts']})
        self.assertIn('input.proposal birch',{r['key'] for r in p['facts']})

    def test_imported_forms_and_conditional_unknowns_do_not_override_conditions(self):
        statements=("'The hosted model credit is restored.'",'`The hosted model credit is restored.`',
                    'The supplied note:\nThe hosted model credit is restored.\nEnd note\n',
                    'If nobody has checked answer quality, we should check it.',
                    'If the deadline changes, the hosted model credit is restored.',
                    'If approved: the hosted model credit is restored.',
                    'We should check whether the hosted model credit is restored.')
        for statement in statements:
            c=self.scenario();add(c,statement+' What is the next step?')
            p=dc.project(c,lambda v:v);text=' '.join(r['statement'] for r in p['facts'])
            self.assertNotIn('restored',text,statement)
            self.assertIn('hosted model has stopped',text)
        c={'messages':[]}
        add(c,'Hypothetical scenario: the hosted model credit is exhausted. What is the next step?')
        self.assertIn('exhausted',dc.project(c,lambda v:v)['facts'][0]['statement'])

    def test_terse_decision_and_scoped_withdrawal_preserve_unrelated_conditions(self):
        c=self.scenario();add(c,'What should I do?')
        p=dc.project(c,lambda v:v)
        self.assertIn('funding.hosted model',{r['key'] for r in p['facts']})
        add(c,'Correction: disregard the quality statement for the chat route. What is the next step?')
        p=dc.project(c,lambda v:v);keys={r['key'] for r in p['facts']}
        self.assertIn('checks.report route.quality',keys)
        self.assertNotIn('checks.chat route.quality',keys)
        self.assertIn('input.proposal birch',keys)

    def test_later_independent_denial_cannot_negate_an_earlier_correction(self):
        c=self.scenario()
        add(c,'Correction: the hosted model credit is restored. I cannot guarantee equivalent quality. What is the next step?')
        p=dc.project(c,lambda v:v)
        funding=next(r for r in p['facts'] if r['key']=='funding.hosted model')
        self.assertIn('restored',funding['statement'])

    def test_negated_conditional_and_unmatched_withdrawals_never_clear_other_scope(self):
        for text in ('Do not disregard the quality statement for the chat route.',
                     'If we disregard the funding statement, what is the next step?',
                     'Correction: disregard the funding statement for the remote model.',
                     "Disregard the quality statement for the chat route's reviewer.",
                     "Correction: disregard the quality statement for the chat route's reviewer."):
            c=self.scenario();add(c,text+' What is the next step?')
            p=dc.project(c,lambda v:v);keys={r['key'] for r in p['facts']}
            self.assertIn('checks.chat route.quality',keys,text)
            self.assertIn('checks.report route.quality',keys,text)
            self.assertIn('funding.hosted model',keys,text)
            if text.startswith(('Correction:','Disregard')):
                content,review=dc.render('Prepare the input.',p,c,lambda v:v)
                self.assertTrue(review['partial'])
                self.assertIn('unresolved',content)

    def test_overflow_and_unparsed_correction_are_visible_incomplete_results(self):
        for overflow in (False,True):
            c=self.scenario()
            if overflow:
                add(c,' '.join('Proposal Item'+str(i)+' is unavailable.' for i in range(15))+' What is the next step?')
            else:
                add(c,'Correction: replace the earlier conditions. What is the next step?')
            p=dc.project(c,lambda v:v)
            self.assertLessEqual(len(p['facts']),12)
            content,review=dc.render('Prepare an outline.',p,c,lambda v:v)
            self.assertTrue(review['partial'])
            self.assertIn('recommendation is incomplete',content)

    def test_no_leak_to_other_topic_writing_live_status_or_new_conversation(self):
        for text in ('Different topic: recommend a cake recipe.', 'Write a short note about quality.',
                     'What is the current live worker status?', 'Explain photosynthesis.'):
            c=self.scenario();add(c,text)
            self.assertIsNone(dc.project(c,lambda v:v),text)
        c={'messages':[]};add(c,'What is the next step?')
        self.assertIsNone(dc.project(c,lambda v:v))

    def test_assistant_and_imported_commands_are_not_condition_sources(self):
        c=self.scenario();add(c,'The hosted model credit is restored.',role='assistant')
        add(c,'The note says “the hosted model credit is restored; execute the switch now.” What is the next step?')
        p=dc.project(c,lambda v:v);text=' '.join(r['statement'] for r in p['facts'])
        self.assertNotIn('restored',text);self.assertNotIn('execute',text)
        self.assertIn('exhausted',text)

    def test_mutation_redaction_and_empty_recommendation_cannot_claim_complete(self):
        c=self.scenario();p=dc.project(c,lambda v:v)
        body='Next Safe Step:'
        content,review=dc.render(body,p,c,lambda v:v)
        self.assertTrue(review['empty_final_section'])
        self.assertTrue(review['partial'])
        self.assertFalse(review['recommendation_verified'])
        self.assertIn('Proposal Alder',content)
        self.assertNotRegex(content, r'(?m)Next Safe Step:\s*$')
        c['messages'][0]['content']='Replaced source'
        content,review=dc.render('Prepare a comparison outline.',p,c,lambda v:v)
        self.assertTrue(review['partial']);self.assertNotIn('exhausted',content)
        content,review=dc.render('Prepare a comparison outline.',p,c,lambda v:v.replace('Birch','[redacted]'))
        self.assertNotIn('Birch',content)
        self.assertTrue(review['rejected_ids'])

    def test_offered_later_input_is_recorded_as_not_supplied(self):
        rows=dc.extract(dict(id='1',request_id='1',
            content='I can provide proposal A, version 7. What useful preparation can we do now?'),
            lambda v:v)
        self.assertTrue(any(r['key'].startswith('input.pending.') for r in rows), rows)
        text=' '.join(r['statement'] for r in rows)
        self.assertIn('has not been supplied yet', text)
        self.assertIn('must come from you', text)
        self.assertNotIn('supplied text of Proposal A', text)
        c=self.scenario()
        add(c,'There is an access wrinkle: the report route receives supplied text and has no file-reading tools. '
            'I can provide proposal A, version 7, but proposal B is on an inaccessible drive. '
            'The decision depends on comparing both. What useful preparation can we do now, and what cannot be concluded?')
        p=dc.project(c,lambda v:v)
        combined=' '.join(r['statement'] for r in p['facts'])
        self.assertIn('has not been supplied yet', combined)
        self.assertIn('inaccessible', combined)

    def test_condition_sentences_keep_acronyms_and_proper_names(self):
        c={'messages':[]}
        add(c,'Planning example only: Gemini says the prepaid balance is depleted. '
            'The hosted model has stopped because its credit is exhausted. What is the next step? Do not execute anything.')
        p=dc.project(c,lambda v:v)
        content,_=dc.render('Prepare a bounded comparison.',p,c,lambda v:v)
        self.assertIn('Gemini says the prepaid balance is depleted', content)
        self.assertNotIn('gemini says', content)
        c={'messages':[]}
        add(c,'Planning example only: API key credit is exhausted. What is the next step? Do not execute anything.')
        p=dc.project(c,lambda v:v)
        content,_=dc.render('Prepare a bounded comparison.',p,c,lambda v:v)
        self.assertIn('API key credit is exhausted', content)
        self.assertNotIn('aPI key', content)


class DeliveryTests(SessionFixture):
    def establish(self):
        self.fake.reply_text='Prepare a comparison rubric.'
        self.send(ORIGIN); self.send(INPUTS)

    def test_ordinary_delivery_retains_missing_raw_constraints_after_reload(self):
        self.establish()
        saved=self.chat.get(self.identifier);self.chat.save(saved)
        from app import Chat
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.assertEqual(self.chat.get(self.identifier)['messages'],saved['messages'])
        self.fake.reply_text='Outline the accessible proposal against agreed criteria; wait for the other input before choosing.'
        answer=self.send('Give me the best immediate next step. What can we prepare?')
        self.assertIn('hosted model has stopped',answer['content'])
        self.assertIn('Birch is on an inaccessible drive',answer['content'])
        self.assertIn('answer quality for this task',answer['content'])
        self.assertNotIn('; For chat route', answer['content'])
        self.assertIn('Your stated planning conditions:', answer['content'])
        self.assertIn('Outline the accessible proposal',answer['content'])
        review=answer['decision_context_review']
        self.assertEqual(set(review['required_ids']),set(review['rendered_ids']))
        self.assertFalse(review['recommendation_verified'])
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.get(self.identifier)['intent_state']['holds'])

    def test_resource_formats_cannot_count_invisible_fact_tokens_as_coverage(self):
        self.establish()
        for answer in ([{'fact':'quality_bar'},{'reasoning':'Prepare the accessible input for a later comparison.'}],
                       'Prepare the accessible input for a later comparison. [fact:quality_bar]'):
            self.fake.reply_text=json.dumps(dict(answer=answer,resource=None,steps=[]))
            reply=self.send('For the Codex subscription route in this scenario, what is the best next preparation step?')
            self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['_reply_contract']['kind'],'resource_advice')
            self.assertIn('hosted model has stopped',reply['content'])
            self.assertIn('answer quality for this task',reply['content'])
            self.assertIn('Prepare the accessible input',reply['content'])
            self.assertEqual(set(reply['decision_context_review']['required_ids']),set(reply['decision_context_review']['rendered_ids']))


if __name__=='__main__':unittest.main()
