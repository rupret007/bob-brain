#!/usr/bin/env python3
"""Metered Gemini/MiniMax calls for web chat without conductor lane locks."""
import inspect
import json
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


def split_transport(raw):
    marker = "\n---BOB_VISION_JSON---\n"
    if marker not in raw:
        return raw, []
    head, prompt = raw.split(marker, 1)
    try:
        vision = json.loads(head).get("vision") or []
    except (json.JSONDecodeError, AttributeError):
        vision = []
    return prompt, vision


def main():
    lane = sys.argv[1]
    if lane not in ("gemini", "minimax"):
        return 2
    prompt, vision = split_transport(sys.stdin.read())
    if not prompt.strip():
        print("empty prompt", file=sys.stderr)
        return 1
    load_keys()
    import budget
    from billing import enforce_chat_cap
    enforce_chat_cap(budget)
    from api import model_call
    from lanes import slot

    with slot(lane):
        budget.check(lane)
        kwargs = {"purpose": "webchat"}
        if "vision" in inspect.signature(model_call).parameters:
            kwargs["vision"] = vision or None
        answer = strip_reply_tags(model_call(lane, prompt, **kwargs))
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
