#!/usr/bin/env python3
"""Metered Gemini/MiniMax calls for web chat without conductor lane locks."""
import os
import re
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("BOB_ROOT", CODE_ROOT.parent)).resolve()
sys.path.insert(0, str(CODE_ROOT / "services"))


def load_keys():
    path = ROOT / "conductor" / "keys.env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        name, sep, value = line.removeprefix("export ").partition("=")
        if sep and re.fullmatch(r"[A-Z_][A-Z0-9_]*", name.strip()):
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def strip_reply_tags(text):
    match = re.search(r"<bob-webchat-reply>\s*(.*?)\s*</bob-webchat-reply>", text, re.S)
    if match and match[1].strip():
        return match[1].strip()
    if "<bob-webchat-reply>" in text or "</bob-webchat-reply>" in text:
        raise RuntimeError("incomplete bob-webchat-reply envelope")
    return text.strip()


def main():
    lane = sys.argv[1]
    if lane not in ("gemini", "minimax"):
        return 2
    prompt = sys.stdin.read()
    if not prompt.strip():
        print("empty prompt", file=sys.stderr)
        return 1
    load_keys()
    import budget
    from billing import enforce_chat_cap
    enforce_chat_cap(budget)
    from api import model_call

    answer = strip_reply_tags(model_call(lane, prompt, purpose="webchat"))
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
