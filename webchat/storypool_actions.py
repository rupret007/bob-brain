"""Owner-confirmed StoryPool actions. Never executed by a model or retry path."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess
import sys
import time

from failover import atomic_json

COMMAND = re.compile(r'^storypool (?:kick (dashboard|watchdog)|queue codex task: ([\s\S]{1,2000}))$', re.I)
CONFIRM = re.compile(r'^(yes|cancel) (wbsp-[a-f0-9]{32})$', re.ASCII)
FORBIDDEN = re.compile(r'\b(?:rad-dad-show-night|grok|merge|undraft|force.push|go.live|send|publish|release|disable.{0,20}(?:guard|test))\b', re.I)
UNAVAILABLE = ('StoryPool action unavailable: cluster coordination or the guarded adapter could not be verified. '
               'No success was confirmed; this approval will not be replayed. Ask for a fresh proposal after checking StoryPool.')


class StoryPoolActions:
    def __init__(self, folder, *, execute=None, clock=time.time):
        self.folder = Path(folder) / 'storypool-actions'
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.execute = execute
        self.clock = clock

    def handle(self, text, conversation_id, request_id, *, actor, allow_effects=True, blocked=False):
        command, control = COMMAND.fullmatch(text), CONFIRM.fullmatch(text)
        if not command and not control and not re.match(r'^storypool (?:kick|queue)\b', text, re.I):
            return None
        if blocked and not (control and control[1] == 'cancel'):
            return 'StoryPool action blocked by your saved chat hold. No action ran.'
        if not actor or not allow_effects:
            return 'StoryPool controls require an authenticated typed owner request without attachments or a worker assignment.'
        with (self.folder / 'receipts.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.folder / 'receipts.json'
            rows = json.loads(path.read_text()) if path.exists() else {}
            if control:
                verb, token = control.groups()
                row = rows.get(token)
                if not row or row['conversation'] != conversation_id or row['actor'] != actor:
                    return 'No matching StoryPool approval in this conversation. Request a fresh proposal.'
                if row['state'] != 'pending':
                    return 'This StoryPool approval was already consumed; no action was repeated.'
                if verb == 'cancel':
                    row['state'] = 'cancelled'
                    atomic_json(path, rows)
                    return 'StoryPool proposal cancelled. No action ran.'
                if request_id == row['request'] or not 0 <= self.clock() - row['created'] <= 300:
                    row['state'] = 'expired'
                    atomic_json(path, rows)
                    return 'StoryPool approval expired or was not a separate message. Request a fresh proposal.'
                # Durable consume precedes the coordination claim and every effect.
                row['state'] = 'claimed'
                atomic_json(path, rows)
                try:
                    if self.execute is None:
                        raise RuntimeError('No guarded adapter')
                    answer = self.execute(dict(row['action']), token)
                    if not isinstance(answer, str):
                        raise RuntimeError('Unverified result')
                except Exception:
                    row['state'] = 'unconfirmed'
                    atomic_json(path, rows)
                    return UNAVAILABLE
                row.update(state='done', result=answer)
                atomic_json(path, rows)
                return answer
            if not command:
                return 'StoryPool controls: storypool kick dashboard; storypool kick watchdog; storypool queue codex task: TASK. Each needs a separate exact approval.'
            service, description = command.groups()
            if description and FORBIDDEN.search(description):
                return 'That task exceeds the draft-only StoryPool action allowlist. No task was queued.'
            action = {'kind': 'kick', 'service': service.lower()} if service else {'kind': 'queue', 'description': description}
            for row in rows.values():
                if row['conversation'] == conversation_id and row['actor'] == actor and row['state'] == 'pending':
                    row['state'] = 'superseded'
            token = 'wbsp-' + secrets.token_hex(16)
            rows[token] = dict(state='pending', actor=actor, conversation=conversation_id,
                               request=request_id, created=self.clock(), action=action)
            atomic_json(path, rows)
            summary = 'restart local ' + service.lower() if service else 'queue a Codex draft task: ' + description
            return ('StoryPool proposal: ' + summary + '. No action has run.\n'
                    'Reply exactly `yes ' + token + '` within 5 minutes, or `cancel ' + token + '`. '
                    'Service execution requires a shared cluster claim. Codex queue execution remains unavailable until its guarded scheduler adapter is verified.')


def guarded_executor(root, *, install=None, data=None):
    """Use the installed StoryPool authority; no local coordination fallback.

    Codex queue mutation is disabled until a scheduler adapter can prove quota,
    pause, lane and exact-head review admission. No legacy queue is substituted.
    """
    install = Path(install or '~/storypool-install').expanduser().resolve()
    data = Path(data or '~/.local/share/storypool').expanduser()

    def execute(action, token):
        if action.get('kind') not in ('kick', 'queue'):
            raise ValueError('Unknown action')
        if action['kind'] == 'kick' and action.get('service') not in ('dashboard', 'watchdog'):
            raise ValueError('Unknown service')
        if action['kind'] == 'queue' and (not isinstance(action.get('description'), str)
                                        or FORBIDDEN.search(action['description'])):
            raise ValueError('Outside draft allowlist')
        if action['kind'] == 'queue':
            return ('Codex task was not queued: the guarded StoryPool scheduler adapter has not been verified. '
                    'No Codex process started and no legacy queue was written. A fresh approval will be needed after integration.')
        if (Path(root) / 'conductor' / 'MAINTENANCE').exists():
            raise RuntimeError('Scheduling paused')
        # Fixed trusted installation, never a path supplied by chat or status files.
        if str(install) not in sys.path:
            sys.path.insert(0, str(install))
        from cluster.control_plane.coordination import ClaimClient, Lease
        from cluster.control_plane.node_control import is_draining
        client = ClaimClient.from_env()
        machine = 'mini' if platform.system() == 'Darwin' else 'nucbox'
        if is_draining(root=data):
            raise RuntimeError('Node draining')
        head = subprocess.run(['git', '-C', str(install), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        task = 'webbob-service-' + action['service']
        claim = client.acquire_task('rupret007/bob-ops-dashboard', task, head, machine)
        with Lease(client, claim) as lease:
            lease.renew()
            from shared_chat import SharedChatContext
            SharedChatContext(data / 'chat').append(
                event_id='storypool-control-' + hashlib.sha256(token.encode()).hexdigest(),
                actor='webbob', summary='Jeff approved a local StoryPool service restart.',
                decisions=('Separate exact owner approval was consumed before the service restart request.',))
            service = action['service']
            if platform.system() == 'Linux':
                args = ['systemctl', '--user', 'restart', 'storypool-' + service + '.service']
                check = ['systemctl', '--user', 'is-active', '--quiet', 'storypool-' + service + '.service']
            elif platform.system() == 'Darwin':
                label = 'gui/' + str(os.getuid()) + '/com.storypool.' + service
                args, check = ['launchctl', 'kickstart', '-k', label], ['launchctl', 'print', label]
            else:
                raise RuntimeError('Unsupported host')
            lease.renew()
            subprocess.run(args, capture_output=True, timeout=10, check=True)
            subprocess.run(check, capture_output=True, timeout=5, check=True)
            return 'Restart requested and local service manager confirmed ' + service + ' is loaded/active. Check StoryPool status for application health.'
    return execute
