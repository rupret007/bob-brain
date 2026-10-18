"""Scoped evidence is immutable and cannot claim unrestricted qualification."""
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import qualification_scope as scope


class ScopeTests(unittest.TestCase):
    def test_owner_admission_and_exact_omissions_are_bound_to_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def write(name,value):
                p=root/name;p.write_text(json.dumps(value))
                return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            admission=write('admission.json',dict(id='continuation',adopted=True))
            steer=write('steer.json',dict(authority_source='Owner defers live voice.',limits_unchanged=True,clock_unchanged=True))
            value=dict(schema=1,continuation_id='continuation',scope_name='nonvoice',
                       deferred_checks=scope.DEFERRED,admission=admission,owner_steer=steer)
            ref=write('scope.json',value)
            with patch.dict('os.environ',{'BOB_QUALIFICATION_SCOPE':json.dumps(ref)}):
                self.assertEqual(scope.selected(),ref)
                result=scope.outcome(True,ref)
                self.assertTrue(scope.passed(result,ref))
                self.assertFalse(scope.passed(result))
                self.assertEqual(result['live_voice']['status'],'NOT RUN')
                Path(steer['path']).write_text('{}')
                with self.assertRaises(RuntimeError):scope.selected()
            extra=write('extra.json',dict(value,deferred_checks=scope.DEFERRED+['remaining-browser']))
            with self.assertRaises(RuntimeError):scope.validate(extra)
            with self.assertRaises(RuntimeError):scope.validate(dict(ref,sha256='0'*64))

    def test_scoped_success_cannot_hide_rollback_or_accept_a_different_scope(self):
        ref=dict(path='/fixture/a',sha256='a');row=scope.outcome(True,ref)
        self.assertFalse(scope.passed(row,dict(path='/fixture/b',sha256='b')))
        for field in ('rolled_back','failure','rollback_error'):
            self.assertFalse(scope.passed(dict(row,**{field:True}),ref))
