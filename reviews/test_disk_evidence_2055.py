"""Disk failure regressions; synthetic faults never fill the real volume."""
import errno
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import texting_deploy_record as record
import deploy_texting_2055 as deploy


class DiskEvidenceTests(unittest.TestCase):
    def test_five_gib_boundary_is_bytes_not_rounded_df(self):
        for free, allowed in ((record.MIN_FREE_BYTES - 1, False), (record.MIN_FREE_BYTES, True)):
            with self.subTest(free=free), patch.object(record, 'disk_space', return_value=dict(minimum_free_bytes=free)):
                if allowed:
                    self.assertEqual(record.require_disk_space('.', '.', 'activation')['minimum_free_bytes'], free)
                else:
                    with self.assertRaises(OSError) as error:
                        record.require_disk_space('.', '.', 'activation')
                    self.assertEqual(error.exception.errno, errno.ENOSPC)

    def test_bounded_stream_preserves_previous_record_and_removes_staging(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
            path = Path(folder) / 'checkpoint.json'
            record.atomic_json(path, {'status': 'previous'})
            with self.assertRaises(OSError) as error:
                record.atomic_json(path, {'context': 'x' * (record.MAX_EVIDENCE_BYTES + 1)})
            self.assertEqual(error.exception.errno, errno.EFBIG)
            self.assertEqual(json.loads(path.read_text()), {'status': 'previous'})
            self.assertFalse(list(Path('/private/tmp').glob('checkpoint.json.*.tmp')))

    def test_fsync_eio_does_not_publish_partial_json(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
            path = Path(folder) / 'checkpoint.json'
            record.atomic_json(path, {'status': 'previous'})
            with patch.object(record.os, 'fsync', side_effect=OSError(errno.EIO, 'synthetic')):
                with self.assertRaises(OSError):
                    record.atomic_json(path, {'status': 'changed'})
            self.assertEqual(json.loads(path.read_text()), {'status': 'previous'})

    def test_compact_observations_preserve_identity_and_hash_without_queue_dumps(self):
        value = dict(sessions=[dict(replay_id='replay', exchanges=[dict(request_id='request',
            pass_check=True, observations=dict(reply=dict(snapshot={'jobs': ['context' * 10000] * 100}),
                                              before=dict(queue_jobs=['context' * 10000] * 100)))])])
        compact = record.compact_evidence(value)
        self.assertLess(len(json.dumps(compact)), 2000)
        self.assertEqual(compact, record.compact_evidence(compact))
        self.assertEqual(deploy.replay_conversations(compact), {'replay'})
        self.assertTrue(compact['sessions'][0]['exchanges'][0]['pass_check'])
        before = compact['sessions'][0]['exchanges'][0]['observations']['before']
        self.assertEqual(before['queue_jobs_digest'], record.json_hash(value['sessions'][0]['exchanges'][0]['observations']['before']['queue_jobs']))

    def test_reserved_blocks_release_and_tiny_marker_survives_atomic_write_failures(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
            path, report = Path(folder) / 'attempt.json', Path(folder) / 'RESULT.md'
            evidence = dict(sha='1' * 40, rollback_version_verified=True)
            record.atomic_json(path, dict(status='LIVE_REPLAY'))
            with patch.object(record, 'RECOVERY_BYTES', 1024**2):
                record.reserve_recovery(path, evidence)
            reserve = Path(evidence['recovery_reserve'])
            self.assertGreaterEqual(reserve.stat().st_blocks * 512, 1024**2)
            record.release_recovery(evidence)
            self.assertFalse(reserve.exists())
            with patch.object(record, 'atomic_json', side_effect=OSError(errno.ENOSPC, 'synthetic')), \
                 patch.object(record, 'atomic_text', side_effect=OSError(errno.EIO, 'synthetic')):
                result = record.failure_publish(path, report, evidence, 'RESULT: FAIL_OR_ROLLBACK\n')
            self.assertEqual(result, str(report))
            self.assertIn('RESULT: FAIL_OR_ROLLBACK', report.read_text())
            self.assertIn('rollback_verified: True', report.read_text())
            self.assertEqual(json.loads(path.read_text())['status'], 'LIVE_REPLAY')

    def test_cancel_io_error_does_not_prevent_restore_attempt(self):
        evidence = dict(previous_version=dict(sha=deploy.PREVIOUS), snapshots=dict(webchat='snapshot'), sessions=[])
        with patch.object(deploy.task_queue, 'cancel_replay', side_effect=OSError(errno.EIO, 'synthetic')), \
             patch.object(deploy, 'restart', return_value=dict(other_screens_unchanged=True)) as restart, \
             patch.object(deploy, 'verify_pins', return_value={}), \
             patch.object(deploy, 'version_pair', return_value={name:dict(sha=deploy.PREVIOUS) for name in ('local','public')}):
            self.assertFalse(deploy.restore_release(Path('.'), evidence))
        restart.assert_called_once()
        self.assertTrue(evidence['rollback_version_verified'])
        self.assertIn('cancel:', evidence['rollback_error'])


if __name__ == '__main__':
    unittest.main()
