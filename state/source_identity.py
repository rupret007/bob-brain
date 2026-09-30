"""Bound bounded local execution evidence to the code bytes actually inspected."""
import hashlib
import json
from pathlib import Path

PATHS = ('webchat/task_dispatch.py', 'webchat/reply_authority.py', 'webchat/answer_intent.py',
         'webchat/providers.py', 'state/task_queue.py', 'webchat/self_improvement.py',
         'webchat/conversation_focus.py', 'services/mini_worker.py', 'services/dispatch_worker.py')
PATHS += ('state/source_identity.py', 'webchat/improvement_investigation.py')
PATHS += ('webchat/app.py', 'webchat/chat_intent.py', 'webchat/dispatch_receipts.py')


def fingerprint(root, suite):
    hashes = {}
    for relative in (*PATHS, suite):
        path = Path(root) / relative
        if path.is_symlink() or path.stat().st_size > 200000:
            raise ValueError('Execution source unavailable or oversized: ' + relative)
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(suite=suite, source_hashes=hashes,
                sha256=hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest())
