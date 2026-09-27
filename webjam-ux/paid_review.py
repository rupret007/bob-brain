#!/usr/bin/env python3
"""Compatibility UX review; all calls share the conductor MiniMax ledger/lease."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from api import model_call
from budget import import_ux_ledger
from lanes import RULES
from state import atomic_write, lock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('number', type=int)
    parser.add_argument('prompt', type=Path)
    parser.add_argument('--max-tokens', type=int, default=8192)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 32000:
        raise ValueError('max-tokens outside review guard')
    import_ux_ledger()
    output = Path(__file__).resolve().parent / ('pass-%03d.md' % args.number)
    if output.exists():
        raise RuntimeError('pass already exists; no duplicate request')
    with lock('lane-minimax', blocking=False):
        answer = model_call('minimax', RULES + args.prompt.read_text(), max_tokens=args.max_tokens, purpose='ux-pass')
        atomic_write(output, answer + '\n')
    print(str(output))


if __name__ == '__main__':
    main()
