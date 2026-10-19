"""Regression coverage for Mini Codex launch and resume refusals."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

MINI = Path(__file__).resolve().parents[1] / 'ops/lane-ops/mini'
LW = MINI / 'lane-wt-logs'


class NucboxOnly(unittest.TestCase):
    def test_no_mini_codex_commands(self):
        for path in MINI.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                with self.subTest(path=path):
                    self.assertIsNone(re.search(r'\bcodex\s+exec\b|\bcodex-linux\b', path.read_text()))

    def test_fill_refuses_releases_and_keeps_queue(self):
        # Execute the actual launch case in a bounded loop, with remote/process commands trapped.
        source = (LW / 'fill.sh').read_text()
        case = source.split('  case $prov in\n', 1)[1].split('\n  esac', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            claims = home / 'Documents/bob-overnight-inject/coord/claims'
            claims.mkdir(parents=True)
            released = claims.parent / 'claims-released'
            released.mkdir()
            claim = claims / 'job.json'
            claim.write_text('{}')
            queue = home / 'fill.queue'
            queue.write_text('job\n')
            script = '''
L=$HOME/log; claimf=$HOME/Documents/bob-overnight-inject/coord/claims/job.json
prov=codex; tier=high; j=job; REL=''; CODEX_HIGH_EFFORT=high
codex_host_pick(){ echo mini; }
sleep(){ echo "$1" > "$HOME/sleep"; }
screen(){ echo launched > "$HOME/launched"; }
q_remove(){ echo removed > "$HOME/removed"; }
for attempt in 1; do
  case $prov in
''' + case + '''
  esac
  q_remove "$j"
done
'''
            result = subprocess.run(['zsh', '-c', script], env=dict(os.environ, HOME=tmp),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('fill codex REFUSED host=mini (NucBox-only)', (home / 'log').read_text())
            self.assertFalse(claim.exists())
            self.assertTrue((released / claim.name).exists())
            self.assertEqual((home / 'sleep').read_text().strip(), '120')
            self.assertEqual(queue.read_text(), 'job\n')
            self.assertFalse((home / 'removed').exists())
            self.assertFalse((home / 'launched').exists())

    def test_nuc_lane_codex_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, LANE_LOG_DIR=tmp, LANE_GUARD=tmp + '/absent',
                       NUC_SSH='false', LANE_PROVIDER='codex')
            result = subprocess.run(['bash', str(LW / 'nuc-lane.sh'), '--inner',
                                     'job', 'repo', 'branch', 'main', 'work'],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn('MINI-CODEX REFUSED', (Path(tmp) / 'job.log').read_text())

    def test_dispatch_never_resumes_or_starts_local_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            logs = home / 'lane-wt/logs'
            logs.mkdir(parents=True)
            for resumed in (False, True):
                with self.subTest(resumed=resumed):
                    if resumed:
                        (logs / 'turd.resumed').touch()
                    script = '''
sysctl(){ echo '{ 0.0 0.0 0.0 }'; }
screen(){ [[ $1 == -ls ]] && return 1; echo launched > "$HOME/launched"; }
pkill(){ echo resumed > "$HOME/resumed"; }
kill(){ echo resumed > "$HOME/resumed"; }
. "$1"
'''
                    result = subprocess.run(['zsh', '-c', script, 'test', str(LW / 'dispatch.sh')],
                                            env=dict(os.environ, HOME=tmp), capture_output=True,
                                            text=True, timeout=10)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn('MINI-CODEX REFUSED', (logs / 'dispatch.log').read_text())
                    self.assertFalse((home / 'launched').exists())
                    self.assertFalse((home / 'resumed').exists())
                    self.assertFalse((logs / 'amv.started').exists())
