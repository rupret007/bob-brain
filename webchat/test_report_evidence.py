"""Collector evidence identifies observed bytes and health without extra effects."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import project_reports
import source_evidence


class CollectorEvidenceTests(unittest.TestCase):
    def test_manifest_verifies_committed_bytes_and_rejects_changed_or_linked_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();repo=root/'bob-brain';repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL,text=True).strip()
            git('init','-b','draft/fixture');(repo/'webchat').mkdir()
            (repo/'webchat/build_info.py').write_text('# identity fixture\n')
            content=repo/'content.txt';content.write_text('verified evidence\n')
            git('add','.');git('-c','user.name=Test','-c','user.email=test@localhost','commit','-m','fixture')
            initial=source_evidence.verify(root,repo)
            self.assertTrue(initial['verified']);self.assertEqual(initial['files_checked'],2)
            content.write_text('uncommitted substitution\n')
            self.assertFalse(source_evidence.verify(root,repo)['verified'])
            outside=root/'outside';outside.write_text('verified evidence\n')
            content.unlink();content.symlink_to(outside)
            self.assertFalse(source_evidence.verify(root,repo)['verified'])

    def test_health_reads_only_dedicated_endpoint_and_discards_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            client=Mock(token='fixture-only')
            client.call.return_value=dict(ok=True,connected=True,sha='f'*40,token='private',contacts=['private'])
            chat=SimpleNamespace(root=root,texting=SimpleNamespace(andrea=client))
            with patch.dict(os.environ,BOB_ROOT=str(root)):
                result=project_reports.bridge_observation(chat)
            client.call.assert_called_once_with('health')
            self.assertEqual(result['status'],'observed')
            self.assertEqual(result['response'],dict(ok=True,connected=True,sha='f'*40))
            self.assertNotIn('private',json.dumps(result))
            client.reset_mock();client.call.side_effect=TimeoutError('private transport details')
            with patch.dict(os.environ,BOB_ROOT=str(root)):
                failed=project_reports.bridge_observation(chat)
            self.assertEqual(failed['status'],'unavailable');self.assertNotIn('private transport',json.dumps(failed))
            client.reset_mock()
            with patch.dict(os.environ,BOB_ROOT=str(root/'different')):
                isolated=project_reports.bridge_observation(chat)
            client.call.assert_not_called();self.assertEqual(isolated['status'],'unconfigured')
