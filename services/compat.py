#!/usr/bin/env python3
"""Single metered entry for legacy ask, architecture and tip-review helpers."""
import argparse
import sys
from pathlib import Path

from lanes import ask
from state import atomic_write


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("lane", choices=("minimax", "gemini"))
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("-f", "--file", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--tip", action="store_true")
    args = parser.parse_args(argv)
    prompt = args.file.read_text() if args.file else (args.prompt if args.prompt not in (None, "-") else sys.stdin.read())
    if not prompt.strip():
        raise RuntimeError("empty prompt")
    if args.tip:
        marker = "VERDICT: PASS or VERDICT: BLOCKED" if args.lane == "minimax" else "ASSESS_OK or ASSESS_BLOCKED"
        prompt = "Review this evidence. Begin with " + marker + "; then give concise findings.\n" + prompt
    answer = ask(args.lane, prompt, purpose="legacy-helper")
    if args.out:
        atomic_write(args.out, answer + "\n")
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
