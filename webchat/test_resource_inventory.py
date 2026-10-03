"""Quota freshness and conversational resource questions, without account calls."""
import json
import time
import uuid
from unittest.mock import patch

from test_webchat import Fixture
import capabilities
import resource_inventory as inventory
import reply_authority
import task_queue


class ResourceInventoryTests(Fixture):
    def test_unknown_and_stale_usage_are_not_promoted_to_current_capacity(self):
        data=inventory.observe(self.root,now=2000)
        self.assertTrue(all(r['observation']['freshness']=='unknown' for r in data['resources']))
        target=self.root/inventory.OBSERVATION; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(dict(version=1,resources={'codex':dict(observed_at=1000,
            authenticated=True,auth_mode='chatgpt',remaining_usage=dict(used_percent=16,credit_units='4121.3'),
            secret='must not project') })))
        codex=next(r for r in inventory.observe(self.root,now=2000)['resources'] if r['name']=='codex')
        self.assertEqual(codex['observation']['freshness'],'stale_or_unknown')
        self.assertNotIn('secret',codex['observation'])
        self.assertEqual(codex['observation']['remaining_usage']['credit_units'],'4121.3')
        codex=next(r for r in inventory.observe(self.root,now=1001)['resources'] if r['name']=='codex')
        self.assertEqual(codex['observation']['freshness'],'recent')
        codex=next(r for r in inventory.observe(self.root,now=999)['resources'] if r['name']=='codex')
        self.assertEqual(codex['observation']['freshness'],'stale_or_unknown')

    def test_resource_questions_reach_reasoning_with_inventory_and_never_queue(self):
        for text in ('What resources are genuinely usable?', 'Which subscriptions can we use without reducing quality?',
                     'How do we use our existing tools without paying twice?'):
            with self.subTest(text=text):
                self.assertTrue(capabilities.needs_grounding(text))
                before=len(self.fake.calls)
                self.chat.submit(self.identifier,text,str(uuid.uuid4())); self.wait()
                self.assertEqual(len(self.fake.calls),before+1)
                self.assertFalse(task_queue.tasks(self.root))
        metadata=capabilities.grounding(self.root,['gemini'],self.identifier)
        self.assertEqual({r['name'] for r in metadata['resources']['resources']},set(inventory.ROUTES))
        self.assertIn('bounded subscription reports',[c['name'] for c in metadata['capabilities']])

    def test_resource_answer_is_not_replaced_by_idle_status(self):
        answer=dict(provider='gemini',content='Use the supported report route for a bounded investigation. Remaining quota is unknown.')
        with patch.object(reply_authority,'operational_reply',side_effect=AssertionError('Do not replace with status')):
            output=reply_authority.enforce(self.root,'What resources are genuinely usable?',answer,self.chat.get(self.identifier))
        self.assertEqual(output,answer['content'])

    def test_ordinary_handoff_draft_does_not_require_executor_report(self):
        text='Prepare a handoff for Dot to review this finding: context should survive reload. I will relay it myself; do not contact Dot.'
        self.chat.submit(self.identifier,text,str(uuid.uuid4())); self.wait()
        self.assertTrue(self.fake.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertNotIn('_project_handoffs',self.chat.get(self.identifier))
