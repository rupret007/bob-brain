"""Voice failure evidence survives fixture deletion without retaining private data."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import voice_probe


class FailureEvidenceTests(unittest.TestCase):
    def test_allowlisted_metadata_and_hashes_only(self):
        secret = 'private context or secret token'
        chat = SimpleNamespace(lock=threading.RLock(),conversations={'id':dict(id=secret,messages=[
            dict(role='assistant',status='done',provider='gemini',content=secret,request_id=secret,
                 voice_interrupted=True,token=secret),
            dict(role=secret,status=secret,provider=secret,content='partial',task_ids=['job'])])},
            voice=SimpleNamespace(calls={'call':dict(owner=secret,conversation_id=secret,ended=True,tools={'turn':secret})}))
        proof=voice_probe.fixture_failure(chat)
        self.assertNotIn(secret,json.dumps(proof))
        row=proof['conversations'][0]['messages'][0]
        self.assertEqual(row['content_sha256'],hashlib.sha256(secret.encode()).hexdigest())
        self.assertTrue(row['voice_interrupted'])
        self.assertEqual(proof['conversations'][0]['messages'][1]['provider'],'other')
        self.assertTrue(proof['calls'][0]['ended'])
        self.assertEqual(proof['calls'][0]['request_hashes'],[row['request_sha256']])

    def test_failed_browser_keeps_original_error_and_metadata_after_fixture_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'proof';private_paths=[]
            error=subprocess.CalledProcessError(1,['node','voice-proof'])
            real_run=subprocess.run
            def run(argv,**kwargs):
                if argv[0]=='node':
                    private_paths.append(Path(kwargs['env']['BOB_VOICE_PROOF_ROOT']))
                    raise error
                if argv[0] not in ('say','ffmpeg'):
                    return real_run(argv,**kwargs)
            with patch.object(voice_probe.subprocess,'run',side_effect=run):
                with self.assertRaises(subprocess.CalledProcessError) as caught:
                    voice_probe.probe(root,output,engines=('chromium',))
            self.assertIs(caught.exception,error)
            self.assertTrue(private_paths and all(not p.exists() for p in private_paths))
            proof=json.loads((output/'fixture-failure.json').read_text())
            self.assertEqual(proof['scope'],'owned isolated fixture only')
            self.assertIn('sha',proof)
            self.assertNotIn('password',json.dumps(proof))


if __name__ == '__main__':
    unittest.main()
