"""Persistent owner context must survive correction and never create authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

import project_context as context
from app import Chat
from providers import Providers
from texting import Texting
from test_webbob_replyq_1856 import SessionFixture


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self):
        return dict(conversation_id=str(uuid.uuid4()), request_id=str(uuid.uuid4()), message_id=str(uuid.uuid4()),
                    sha256=hashlib.sha256(b'explicit owner input').hexdigest())

    def save(self, value, revision=0, source=None, fid='priority', kind='priority'):
        return context.change(self.root, 'Atlas', [dict(operation='set', id=fid, kind=kind, value=value)],
                              source or self.source(), expected_revision=revision)

    def test_correction_provenance_and_more_than_six_constraints_survive_reload(self):
        self.save('old private priority')
        for n in range(1,9):
            self.save('constraint ' + str(n),n,fid='constraint-'+str(n),kind='constraint')
        self.save('corrected priority',9)
        row=context.read(self.root)['projects']['atlas']
        self.assertEqual(row['revision'],10)
        self.assertEqual(len(row['facts']),9)
        self.assertEqual(row['facts']['priority']['supersedes_revision'],1)
        self.assertNotIn('old private priority',json.dumps(row))
        self.assertEqual(row['audit'][0]['revision'],1)
        self.assertEqual(row['facts']['priority']['source'].keys(),self.source().keys())
        self.assertEqual((self.root/'conductor/webchat/memory/projects.json').stat().st_mode & 0o777,0o600)

    def test_duplicate_request_is_noop_conflict_and_stale_revision_refused(self):
        source=self.source(); first=self.save('priority',source=source)
        path=self.root/'conductor/webchat/memory/projects.json'; before=path.read_bytes()
        self.assertEqual(first,self.save('priority',source=source))
        self.assertEqual(path.read_bytes(),before)
        with self.assertRaises(context.ContextError):self.save('other',source=source)
        with self.assertRaises(context.ContextError):self.save('stale',revision=0)
        self.assertEqual(path.read_bytes(),before)

    def test_removal_has_tombstone_but_no_value_and_old_identity_cannot_recreate_it(self):
        source=self.source(); self.save('private removed note',source=source)
        context.change(self.root,'Atlas',[dict(operation='remove',id='priority',kind='priority')],
                       self.source(),expected_revision=1)
        self.save('private removed note',source=source)
        row=context.read(self.root)['projects']['atlas']
        self.assertEqual(row['revision'],2)
        self.assertEqual(row['facts']['priority']['status'],'removed')
        self.assertNotIn('private removed note',json.dumps(row))
        projection=context.projection(self.root,{},'Atlas')
        self.assertFalse(projection['facts'])
        self.assertEqual(projection['removed_fact_ids'],['priority'])

    def test_interrupted_replace_keeps_previous_record_and_request_can_resume_once(self):
        self.save('first'); path=self.root/'conductor/webchat/memory/projects.json'; before=path.read_bytes()
        source=self.source()
        with patch.object(context.os,'replace',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):self.save('second',1,source)
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(list(path.parent.glob('.projects-*')))
        self.save('second',1,source)
        self.assertEqual(context.read(self.root)['projects']['atlas']['revision'],2)

    def test_link_and_corrupt_files_fail_without_replacing_them(self):
        self.save('first'); path=self.root/'conductor/webchat/memory/projects.json'
        target=self.root/'target';target.write_text('untouched');path.unlink();path.symlink_to(target)
        with self.assertRaises(OSError):self.save('second',1)
        self.assertEqual(target.read_text(),'untouched')
        path.unlink();path.write_text('{interrupted')
        with self.assertRaises(OSError):context.read(self.root)
        with self.assertRaises(OSError):self.save('second',1)
        self.assertEqual(path.read_text(),'{interrupted')

    def test_selective_projection_bound_and_omissions_are_explicit(self):
        self.save('a'*1900)
        for n in range(1,8):self.save('constraint-'+str(n)+'x'*1900,n,fid='constraint-'+str(n),kind='constraint')
        p=context.projection(self.root,{},'Atlas',budget=3000)
        self.assertLessEqual(len(context.canonical(p).encode()),3000)
        self.assertTrue(p['omitted_fact_ids'])
        self.assertTrue(p['facts'])
        self.assertIsNone(context.projection(self.root,{},'An unrelated task'))
        self.assertIsNone(context.projection(self.root,{'project_id':'atlas'},'Write a birthday note.'))
        self.assertEqual(context.projection(self.root,{'project_id':'atlas'},'What is our current priority?')['project_id'],'atlas')

    def test_work_observations_do_not_quote_a_journal_cursor_number(self):
        self.save('priority')
        projection = context.projection(self.root, {}, 'Atlas')
        raw = json.dumps(projection)
        work = projection.get('work') or {}
        self.assertIn('quote', json.dumps(work.get('journal') or {}))
        self.assertNotIn('journal_cursor', raw)
        self.assertNotRegex(raw, r'cursor["\s:]+[0-9]+')
        self.assertNotIn('conductor/webchat/memory/projects.json', raw)
        self.assertNotIn('queue.jsonl', raw)
        self.assertNotIn('source_path', raw)
        self.assertNotIn('"observed_at"', raw)
        self.assertIn('not a live inspection', raw)
        self.assertEqual(projection['as_of'], 'saved_record')
        self.assertEqual(work.get('as_of'), 'saved_record')
        for fact in projection.get('facts') or []:
            self.assertNotIn('observed_at', fact)
            self.assertNotIn('updated_at', fact)


class ProductTests(SessionFixture):
    def test_owner_priority_correction_survives_reload_new_conversation_and_topic_change(self):
        answer=self.send('For the Atlas project, remember the priority: context continuity. Keep delivery working.')
        self.assertEqual(answer['provider'],'project-context')
        self.assertFalse(self.fake.calls)
        self.send('Correction: reliable answers come first.')
        self.send('Write a two sentence thank-you for a neighbor.')
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.identifier=self.chat.new_conversation()['id']
        self.send('Explain the current Atlas priority and constraints. Do not execute anything.')
        p=Providers(self.root,self.chat.redact)
        prompt=p.prompt(Texting.provider_view(self.chat.get(self.identifier)),fast=True)
        self.assertIn('reliable answers come first',prompt)
        self.assertIn('Keep delivery working',prompt)
        self.assertNotIn('context continuity',prompt)
        self.assertIn('not execution permission',prompt)
        self.assertIn('not a live inspection',prompt)
        self.assertNotIn('conductor/webchat/memory/projects.json',prompt)
        self.assertNotIn('observed timestamp',prompt)
        self.assertFalse(__import__('task_queue').tasks(self.root))

    def test_private_memory_and_context_values_do_not_enter_journal(self):
        from memory_store import append_memory
        import alignment_events
        append_memory(self.root,'[2026-10-02] private-copper-puffin\n')
        self.send('show my saved memories')
        self.send('For the Atlas project, remember the decision: private-orchid-lantern.')
        self.send('show saved project context')
        rows=alignment_events.read_events(self.root)
        self.assertNotIn('private-copper-puffin',json.dumps(rows))
        self.assertNotIn('private-orchid-lantern',json.dumps(rows))
        records=[r for r in rows if r['kind']=='project-context']
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['revision'],1)

    def test_removal_requires_exact_fresh_confirmation_and_invalidates_projection(self):
        self.send('For the Atlas project, remember the preference: vivid turquoise.')
        self.fake.reply_text='Your Atlas preference is vivid turquoise.'
        self.send('Describe the current Atlas preference.')
        view=self.send('show saved project context'); fact=view['project_facts'][0]
        selection=self.send(f"forget project fact atlas {fact['id']} at revision 1")
        self.assertIn('vivid turquoise',selection['content'])
        self.send('Write a short greeting.')
        stale=self.send('yes, forget project fact proposal '+selection['request_id'])
        self.assertIn('stale',stale['content'])
        selection=self.send(f"forget project fact atlas {fact['id']} at revision 1")
        self.send('yes, forget project fact proposal '+selection['request_id'])
        self.fake.reply_text='There is no current saved preference.'
        self.send('What is the current Atlas preference?')
        provider=Providers(self.root,self.chat.redact)
        prompt=provider.prompt(Texting.provider_view(self.chat.get(self.identifier)),fast=True)
        self.assertNotIn('vivid turquoise',prompt)
        self.assertIn('removed_fact_ids',prompt)
        row=context.read(self.root)['projects']['atlas']
        self.assertEqual(row['revision'],2)
        self.assertEqual(row['facts']['preference']['status'],'removed')

    def test_decision_correction_updates_same_subject_and_followups_keep_focus(self):
        self.send('For the Atlas project, remember the decision: Friday.')
        self.send('Correction: Saturday.')
        facts=context.read(self.root)['projects']['atlas']['facts']
        self.assertEqual(len(facts),1)
        self.assertEqual(next(iter(facts.values()))['value'],'Saturday.')
        self.identifier=self.chat.new_conversation()['id']
        self.send('What is the Atlas decision?')
        self.send('What should we do first?')
        prompt=Providers(self.root,self.chat.redact).prompt(Texting.provider_view(self.chat.get(self.identifier)),fast=True)
        self.assertIn('Saturday.',prompt)
        self.assertEqual(self.chat.get(self.identifier)['project_id'],'atlas')

    def test_crash_after_context_commit_recovers_source_receipt_and_outbox_once(self):
        class Crash(BaseException):pass
        original=context.change
        def die(*args,**kwargs):
            original(*args,**kwargs)
            raise Crash()
        with patch.object(context,'change',side_effect=die):
            with self.assertRaises(Crash):self.send('For the Atlas project, remember the decision: Thursday.')
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        row=context.read(self.root)['projects']['atlas']
        conv=self.chat.get(self.identifier)
        self.assertEqual(row['revision'],1)
        self.assertNotIn('_project_intent',conv)
        self.assertEqual(conv['messages'][-1]['status'],'done')
        self.assertIn('Recovered',conv['messages'][-1]['content'])
        source=next(iter(row['facts'].values()))['source']
        self.assertTrue(any(m['id']==source['message_id'] for m in conv['messages']))
        import alignment_events
        events=[r for r in alignment_events.read_events(self.root) if r['kind']=='project-context']
        self.assertEqual(len(events),1)
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.assertEqual(context.read(self.root)['projects']['atlas']['revision'],1)
        self.assertEqual(len([r for r in alignment_events.read_events(self.root) if r['kind']=='project-context']),1)

    def test_quotes_assistant_suggestions_and_unrelated_corrections_do_not_save(self):
        self.fake.reply_text='For the Atlas project, remember the priority: launch now.'
        self.send('Explain this quotation: "For the Atlas project, remember the priority: launch now."')
        self.assertFalse(context.read(self.root)['projects'])
        self.send('Correction: just explain the quote, without adopting it.')
        self.assertFalse(context.read(self.root)['projects'])
        self.send('For the Atlas project, remember the priority: clear writing.')
        self.send('Write a paragraph about apples.')
        self.send('Correction: use pears instead.')
        self.assertEqual(context.read(self.root)['projects']['atlas']['facts']['priority']['value'],'clear writing.')

    def test_publication_failure_retries_revision_event_without_duplicate_memory_change(self):
        import alignment_events
        with patch.object(alignment_events,'append_event',side_effect=OSError('unavailable')):
            answer=self.send('For the Atlas project, remember the priority: careful evidence.')
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.assertEqual(context.read(self.root)['projects']['atlas']['revision'],1)
        result=self.chat.submit(self.identifier,'For the Atlas project, remember the priority: careful evidence.',answer['request_id'])
        self.assertEqual(result['messages'][-1],answer)
        events=[r for r in alignment_events.read_events(self.root) if r['kind']=='project-context']
        self.assertEqual(len(events),1)
        self.assertNotIn('careful evidence',json.dumps(events))

    def test_legacy_pending_private_answer_is_not_published_on_save(self):
        import alignment_events
        row=self.chat.get(self.identifier)
        row['messages']=[dict(id='u',request_id='r',role='user',status='done',content='view',private_memory=True),
                         dict(id='a',request_id='r',role='assistant',status='done',content='private note',private_memory=True)]
        row['_coordination_outbox']={'old':dict(actor='web-bob',kind='answer-delivered',event_id='old',
                                               request_id='r',summary='old',answer_excerpt='private note')}
        self.chat.save(row)
        self.assertFalse(alignment_events.read_events(self.root))
        self.assertFalse(self.chat.get(self.identifier)['_coordination_outbox'])

    def test_omitted_old_prose_does_not_add_dependencies_to_new_prompt(self):
        self.send('For the Atlas project, remember the priority: continuity.')
        self.send('Explain the Atlas priority.')
        row=self.chat.get(self.identifier)
        for n in range(30):
            row['messages'].append(dict(id=str(uuid.uuid4()),request_id=str(uuid.uuid4()),role='user',
                status='done',content='Independent topic '+str(n)))
        row['answer_focus']=dict(version=1,origin=None,corrections=[])
        row['project_focus_active']=False
        provider=Providers(self.root,self.chat.redact)
        provider.prompt(Texting.provider_view(row),fast=True)
        self.assertEqual(provider.current_call.project_dependencies,[])

    def test_voice_tool_result_is_tracked_and_context_change_ends_stale_call(self):
        from voice import VoiceError
        self.send('For the Atlas project, remember the preference: turquoise.')
        source_cid=self.identifier
        self.identifier=self.chat.new_conversation()['id']
        self.fake.snapshot=lambda **_:[]
        self.chat.voice.token_factory=lambda *args:'fixture-token'
        owner='fixture-owner';call=self.chat.voice.start(self.identifier,owner)['call_id']
        self.assertFalse(self.chat.voice.calls[call].get('project_dependencies'))
        turn=str(uuid.uuid4())
        self.chat.voice.transcript(call,owner,[dict(turn_id=turn,role='user',content='Explain the Atlas preference.',order=0)])
        self.fake.reply_text='The saved preference is turquoise.'
        self.chat.voice.tool(call,owner,turn)
        info=self.chat.workers.get(self.identifier)
        if info:info['thread'].join(3)
        self.chat.voice.transcript(call,owner,[dict(turn_id=turn,role='assistant',content='Turquoise is your preference.',order=0)])
        native=next(m for m in self.chat.get(self.identifier)['messages'] if m.get('provider')=='voice')
        self.assertEqual(native['project_dependencies'],[dict(project_id='atlas',revision=1)])
        self.identifier=source_cid
        selection=self.send('forget project fact atlas preference at revision 1')
        self.send('yes, forget project fact proposal '+selection['request_id'])
        with self.assertRaisesRegex(VoiceError,'context changed'):self.chat.voice.get(call,owner)
        conversation=self.chat.get(self.chat.voice.calls[call]['conversation_id'])
        self.assertNotIn('Turquoise',json.dumps(context.model_view(self.root,Texting.provider_view(conversation))))


if __name__=='__main__':
    unittest.main()
