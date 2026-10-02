"""Owned-process cleanup and cancellation; no network, providers or jobs."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

import api
import command


class CleanupTests(unittest.TestCase):
    def test_permission_error_requires_verified_terminal_group(self):
        for rows, code, terminal in (
            ('123 Z\n456 S\n', 0, True), ('456 S\n', 0, True),
            ('123 Z\n123 S\n', 0, False), ('123 S\n', 0, False),
            ('', 1, False), ('malformed', 0, False),
        ):
            with self.subTest(rows=rows, code=code):
                error = PermissionError(1, 'fixture denied')
                with patch.object(command.os, 'killpg', side_effect=error) as send, \
                        patch.object(command.subprocess, 'run', return_value=SimpleNamespace(
                            returncode=code, stdout=rows)):
                    if terminal:
                        command.signal_group(123, signal.SIGKILL)
                    else:
                        with self.assertRaises(PermissionError) as caught:
                            command.signal_group(123, signal.SIGKILL)
                        self.assertIs(caught.exception, error)
                send.assert_called_once_with(123, signal.SIGKILL)
        with patch.object(command.os, 'killpg', side_effect=PermissionError(1, 'denied')), \
                patch.object(command.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ps', 3)):
            with self.assertRaises(PermissionError):
                command.signal_group(123, signal.SIGTERM)

    def test_real_unreaped_group_is_terminal_and_unrelated_child_is_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'identity.json'
            source = ('import subprocess,sys,time,json,os; from pathlib import Path; '
                      'child=subprocess.Popen([sys.executable,"-c","pass"],start_new_session=True); '
                      'Path(sys.argv[1]).write_text(json.dumps(dict(parent=os.getpid(),child=child.pid))); '
                      'time.sleep(30)')
            parent = subprocess.Popen([sys.executable, '-c', source, str(marker)], start_new_session=True)
            unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'], start_new_session=True)
            try:
                deadline = time.monotonic() + 3
                identity = None
                while time.monotonic() < deadline:
                    try:
                        identity = json.loads(marker.read_text())
                        break
                    except (FileNotFoundError, ValueError):
                        time.sleep(.01)
                self.assertIsNotNone(identity)
                child = identity['child']
                while time.monotonic() < deadline:
                    row = subprocess.run(['ps', '-p', str(child), '-o', 'pid=,ppid=,pgid=,uid=,stat=,lstart='],
                                         capture_output=True, text=True, timeout=2).stdout.split()
                    if row and row[4].startswith('Z'):
                        break
                    time.sleep(.01)
                self.assertEqual([int(n) for n in row[:4]], [child, parent.pid, child, os.getuid()])
                self.assertTrue(row[4].startswith('Z'))
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    command.signal_group(child, sig)
                self.assertIsNone(unrelated.poll())
            finally:
                for proc in (parent, unrelated):
                    proc.terminate()
                    proc.wait(timeout=3)

    def test_signal_with_cleanup_failure_cannot_become_an_http_retry(self):
        handlers = {}
        proc = Mock(pid=123, stdout=None, stderr=None)
        def communicate(**kwargs):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
        proc.communicate.side_effect = communicate
        def handler(sig, callback):
            handlers[sig] = callback
            return signal.SIG_DFL
        with patch.object(command.subprocess, 'Popen', return_value=proc) as launch, \
                patch.object(command.signal, 'signal', side_effect=handler), \
                patch.object(command, 'kill_group', side_effect=PermissionError(1, 'fixture cleanup denied')), \
                patch.object(api, 'run', side_effect=command.run), \
                patch.object(api.time, 'sleep') as retry, \
                patch.object(api.budget, 'reserve', return_value={'call_id': 'fixture'}) as reserve:
            with self.assertRaises(SystemExit) as caught:
                api.http_json('https://example.invalid', lane='gemini', prompt='fixture', max_tokens=1, attempts=3)
        self.assertEqual(caught.exception.code, 128 + signal.SIGTERM)
        self.assertIsInstance(caught.exception.__cause__, PermissionError)
        launch.assert_called_once()
        reserve.assert_called_once()
        retry.assert_not_called()

    def test_ordinary_cleanup_permission_error_is_not_reported_as_success(self):
        proc = Mock(pid=123, stdout=None, stderr=None, returncode=0)
        proc.communicate.return_value = ('answer', '')
        with patch.object(command.subprocess, 'Popen', return_value=proc), \
                patch.object(command, 'kill_group', side_effect=PermissionError(1, 'fixture denied')):
            with self.assertRaises(PermissionError):
                command.run(['fixture'], timeout=1)
