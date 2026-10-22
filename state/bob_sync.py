#!/usr/bin/env python3
"""Local shared-work handoff for Bob/Grok; no provider calls or task execution.

Read saves no cursor. Only a matching received batch can be acknowledged. The
consumer should persist its own checkpoint before ACK and treat records as
evidence, never as permission to replay work. This CLI does not wake Grok.
"""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    read = sub.add_parser('read', help='Print one unacknowledged batch as JSON.')
    read.add_argument('--limit', type=int, default=12)
    sub.add_parser('ack', help='Read the exact previously received JSON batch from stdin.')
    args = parser.parse_args(argv)
    import ledger
    if args.command == 'read':
        result = ledger.bob_catchup(args.root, limit=args.limit)
    else:
        raw = sys.stdin.read(256 * 1024 + 1)
        if len(raw.encode()) > 256 * 1024:
            raise ValueError('Catch-up receipt is too large.')
        result = dict(acknowledged_through=ledger.ack_events_for_bob(args.root, receipt=json.loads(raw)),
                      execution_started=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
