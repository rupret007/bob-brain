"""Stdlib-only durable evidence primitives shared by the texting launcher/runner."""
import json
import os
from pathlib import Path
import tempfile


def atomic_text(path, text, *, exclusive=False):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            # Publish a complete first record without replacing another attempt.
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, value, *, exclusive=False):
    atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n', exclusive=exclusive)


def claim_record(path, evidence):
    atomic_json(path, evidence, exclusive=True)


def launch_environment(candidate, root):
    candidate, root = Path(candidate).resolve(), Path(root).resolve()
    return dict(os.environ, BOB_ROOT=str(root), TMPDIR='/private/tmp',
                PYTHONPATH=os.pathsep.join(str(candidate / name)
                    for name in ('webchat', 'services', 'state', 'reviews')))
