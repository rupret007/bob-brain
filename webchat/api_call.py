#!/usr/bin/env python3
"""Metered Gemini/MiniMax calls for web chat without conductor lane locks."""
import base64
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
    try:
        payload = json.loads(raw)
        prompt, vision = payload["prompt"], payload.get("vision", [])
        if not isinstance(prompt, str) or not isinstance(vision, list) or len(vision) > 24:
            raise ValueError()
        for part in vision:
            if not isinstance(part, dict):
                raise ValueError()
            mime = part.get("mime")
            if mime not in ("image/jpeg", "image/png", "image/webp"):
                raise ValueError()
            raw_b64 = part.get("data_base64")
            if not isinstance(raw_b64, str):
                raise ValueError()
            try:
                base64.b64decode(raw_b64, validate=True)
            except ValueError:
                raise ValueError() from None
        return prompt, vision
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("Invalid chat transport payload.") from None


def main():
    lane = sys.argv[1]
    if lane not in ("gemini", "minimax"):
        return 2
    try:
        prompt, vision = split_transport(sys.stdin.read())
    except ValueError:
        print("invalid transport payload", file=sys.stderr)
        return 1
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
        elif vision:
            raise RuntimeError("This API helper does not support vision.")
        answer = strip_reply_tags(model_call(lane, prompt, **kwargs))
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
