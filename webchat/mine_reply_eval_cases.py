#!/usr/bin/env python3
"""Mine reply-quality eval cases from conductor/webchat/sessions/*.json (read-only)."""
from __future__ import annotations

import json
import re
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "reply_eval_cases.json"


def session_dir() -> Path:
    for candidate in (
        CODE_ROOT / "conductor/webchat/sessions",
        CODE_ROOT.parent.parent / "conductor/webchat/sessions",
    ):
        if candidate.is_dir():
            return candidate
    raise SystemExit("No conductor/webchat/sessions directory found for mining.")

SKIP = re.compile(
    r"^Reply with exactly:|^From BOB-STATE and handback only:|^start lane |E2E0927|"
    r"^Debug this chat connection|^Connection check:|^Browser connection check|playwright ping",
    re.I,
)
PATTERNS = [
    ("status", re.compile(
        r"^(status|update\??|what.?s (?:running|going|up)|quick status|anything i need|"
        r"how.*going|is anything running|is it going)", re.I)),
    ("llm", re.compile(
        r"(what'?s working on what|each llm|what is each|going on each|current chat provider|"
        r"resources you have left|what.?s going on what resources|who is answering)", re.I)),
    ("start", re.compile(
        r"(start a job|queue job|push everything|start up|prioritize|go to the max|"
        r"push WebJam|stress test|taking everything to the max)", re.I)),
    ("criticism", re.compile(
        r"(bad reply|more useful than grok|way better|unknown tasks|none of these are really blocked|"
        r"can.t have unknown|detailed updates|needs to be way better)", re.I)),
    ("version", re.compile(r"(what version|build are you|new version|Is this the new version)", re.I)),
    ("hold", re.compile(r"(hold off|on hold|say go|hold is lifted|Are we still on hold|permission before)", re.I)),
    ("text", re.compile(r"(draft (?:a )?(?:text|message|reply)|help me write (?:a )?(?:text|message)|"
                        r"wording for (?:a )?text|sms draft)", re.I)),
    ("typo", re.compile(r"\bwhats working\b|\bwht\b|stkryboard|Stkryboard|\bteh\b", re.I)),
]

MANUAL = [
    ("8126301c", "start", "Ok start up all the projects we were working on taking everything to the max."),
    ("8126301c", "llm", "Ok what's working on what?"),
    ("8126301c", "criticism", "Ok we can't have unknown tasks. We need to also know what's going on what resources."),
    ("8126301c", "criticism", "This needs to be way better"),
    ("8126301c", "llm", "Ok whats working on what?"),
    ("mined", "typo", "Ok we want it to start up at max all the projects we were working on before. Remember. WebJam, Adopt"),
    ("mined", "text", "Help me draft a short text I could send the band about practice — don't send it, just the wording."),
    ("mined", "text", "Draft a reply text for Travis about the gig time; I will send it myself."),
]


def rubrics_for(category: str) -> list[str]:
    base = ["answer_first", "no_unknown_task", "no_magic_prefix", "no_empty_promises"]
    if category in ("status", "llm"):
        base.append("status_max_lines")
    if category == "llm":
        base.append("reset_attribution")
    if category == "start":
        return ["answer_first", "no_magic_prefix", "no_empty_promises", "action_creates_jobs", "not_status_only"]
    if category == "version":
        return ["answer_first", "no_magic_prefix", "version_short_sha"]
    if category == "hold":
        return ["answer_first", "no_magic_prefix", "hold_coherent"]
    if category == "text":
        return ["answer_first", "no_magic_prefix", "no_empty_promises", "draft_only_no_send"]
    if category == "criticism":
        return base
    if category == "typo":
        return rubrics_for("llm")
    return base


def main() -> None:
    cases: list[dict] = []
    seen: set[str] = set()

    def add(category: str, prompt: str, session: str, *, fixture: str | None = None, stub: str | None = None):
        prompt = " ".join(prompt.split())
        if not prompt or prompt in seen or SKIP.search(prompt):
            return
        seen.add(prompt)
        n = sum(1 for c in cases if c["category"] == category) + 1
        row = {
            "id": f"{category}-{n:02d}",
            "category": category,
            "prompt": prompt,
            "session": session,
            "rubrics": rubrics_for(category),
        }
        if fixture:
            row["fixture"] = fixture
        if stub:
            row["stub_model"] = stub
        cases.append(row)

    for session, category, prompt in MANUAL:
        fix = "busy_workers" if category in ("status", "llm", "typo") and "working" in prompt.lower() else None
        stub = (
            "Okay, I'll focus on getting all the projects running at full capacity."
            if category == "start" and "start up all" in prompt
            else "I understand. I'll focus on providing more detailed and useful updates."
            if category == "criticism" and "way better" in prompt
            else None
        )
        add(category, prompt, session, fixture=fix, stub=stub)

    for path in sorted(session_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        session = path.stem[:8]
        for message in data.get("messages", []):
            if message.get("role") != "user":
                continue
            prompt = " ".join((message.get("content") or "").split())
            if len(prompt) < 3 or len(prompt) > 450 or prompt in seen or SKIP.search(prompt):
                continue
            for category, pattern in PATTERNS:
                if pattern.search(prompt):
                    fix = "busy_workers" if category in ("status", "llm") else None
                    add(category, prompt, session, fixture=fix)
                    break

    # Typo category: apostrophe-stripped variants of mined llm prompts
    for case in list(cases):
        if case["category"] != "llm" or "what's" not in case["prompt"].lower():
            continue
        typo = re.sub(r"what's", "whats", case["prompt"], flags=re.I)
        add("typo", typo, case["session"] + "-typo", fixture=case.get("fixture"))

    if len(cases) < 30:
        raise SystemExit(f"Expected 30+ cases, got {len(cases)}")

    OUT.write_text(json.dumps(dict(baseline_sha="dcc2c8e", cases=cases), indent=2) + "\n")
    print(f"Wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
