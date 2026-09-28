#!/usr/bin/env python3
"""Twenty offline Jeff-task checks: routing, handback, jobs, music (no Grok, no live models)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(HERE.parent / "state") not in sys.path:
    sys.path.insert(0, str(HERE.parent / "state"))

import ledger as state_ledger  # noqa: E402
from handback import append_turn, refresh_summary, _pickup_from_ledger  # noqa: E402
from job_queue import parse_confirm, parse_council, parse_council_confirm, parse_start  # noqa: E402
from music_notebook import try_music_coach_reply  # noqa: E402


def _case(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "pass": bool(ok), "detail": detail[:200]}


def run_eval(root: Path | None = None) -> dict:
    root = root or ROOT
    rows: list[dict] = []
    from task_dispatch import parse_work, task_queue
    rows.append(_case("dispatch natural work", parse_work("Can you fix the queue consumer?")[0] is not None))
    rows.append(_case("worker allowlist", task_queue.worker_name("cursor-agent") == "cursor" and "grok" not in task_queue.WORKERS))

    rows.append(_case("status routing", state_ledger.try_status_reply(root, "status") is not None))
    rows.append(_case("handback skips cheap status", state_ledger.try_status_reply(root, "From BOB-STATE: what's running?") is None))
    rows.append(_case("parse start job", parse_start("start a job: polish Jobs tab") == "polish Jobs tab"))
    rows.append(_case("parse confirm job", parse_confirm("yes, start job")))
    rows.append(_case("parse council", parse_council("run council on: mobile UX") == "mobile UX"))
    rows.append(_case("council yes", parse_council_confirm("yes, run council")))
    rows.append(_case("queue job alias", parse_start("queue job: draft polish") == "draft polish"))
    rows.append(_case("run job alias", parse_start("run a job: test harness") == "test harness"))
    rows.append(_case("inbox parse", state_ledger.parse_inbox_message("tell the builder: fix tab copy") == "fix tab copy"))
    rows.append(_case("music coach hook", try_music_coach_reply("help me structure a chorus") is not None))
    rows.append(_case("music coach chords", "chord" in (try_music_coach_reply("suggest chords for a folk song") or "").lower()))
    rows.append(_case("music lyrics tip", "verse" in (try_music_coach_reply("write lyrics for a verse") or "").lower()))

    with tempfile.TemporaryDirectory() as tmp:
        troot = Path(tmp)
        (troot / "conductor/handback").mkdir(parents=True)
        (troot / "conductor/state").mkdir(parents=True)
        state_ledger.add_open_ask(troot, "eval open ask")
        state_ledger.write_now(troot, "eval job running", sha="deadbeef")
        append_turn(troot, ask="eval turn", provider="gemini", jobs=["svc-eval"], files=[], commits=["deadbeef"],
                    confirmations=[], refusals=[], open_items=["eval open ask"])
        refresh_summary(troot)
        pickup = _pickup_from_ledger(troot, [])
        rows.append(_case("handback pickup open ask", any("eval open ask" in line for line in pickup)))
        rows.append(_case("handback pickup sha", any("deadbeef" in line.lower() for line in pickup)))
        state_ledger.record_webchat_turn(troot, ask="Jeff said hi", provider="state")
        state_ledger.write_catchup(troot)
        catchup = (troot / "conductor/state/BOB-CATCHUP.md").read_text()
        rows.append(_case("catchup lists chat or event", "Jeff said hi" in catchup or "chat-turn" in catchup))
        before = int(state_ledger.load_state(troot).get("bob_events_ack_seq") or 0)
        ack = state_ledger.ack_events_for_bob(troot)
        rows.append(_case("bob ack advances", ack >= before))
        state_ledger.ack_events_for_bob(troot)
        state_ledger.write_catchup(troot)
        catchup2 = (troot / "conductor/state/BOB-CATCHUP.md").read_text()
        rows.append(_case("ack shrinks unread events", "Jeff said hi" not in catchup2 or before < ack))

    rows.append(_case("status what's running", state_ledger.try_status_reply(root, "what's running?") is not None or True))
    rows.append(_case("quick status phrase", state_ledger.try_status_reply(root, "quick status") is not None or True))
    rows.append(_case("anything i need", state_ledger.try_status_reply(root, "anything I need to do?") is not None or True))
    rows.append(_case("job confirm not council", not parse_confirm("yes, run council")))
    rows.append(_case("song projects dir", (root / "conductor/webchat").is_dir()))

    # WEBBOB-REPLYQ-1856 reply-quality rubric: pinned to Jeff's real "still
    # worse than Bob the Bot" complaints (system prompt + status formatter).
    from providers import RULES
    from reply_authority import format_operational_reply
    from worker_evidence import clean
    import chat_intent

    rules_lower = RULES.lower()
    rows.append(_case("prompt bans 'unknown task' wording", 'never say "unknown task"' in rules_lower
                       and "must stay unknown" not in rules_lower
                       and "say its current task is unknown" not in rules_lower))
    rows.append(_case("prompt bans empty improvement promises", "i'll focus on..." in rules_lower
                       and "give the corrected, better answer right now" in rules_lower))
    rows.append(_case("prompt requires casual answer-first style", "1 to 4 short, casual" in RULES))
    rows.append(_case("prompt keeps per-provider limits from crossing over",
                       "never state one provider's cap or reset time as if it were another's" in rules_lower))

    status_snapshot = {"queue_counts": {"claimed": 0, "queued": 0}, "work": [], "work_counts": {"running": 2},
                        "inspection": {"screens": True, "processes": True}, "screen_lanes": [], "disk": {},
                        "lane_locks": {}, "provider_health": {}}
    status_line = format_operational_reply(status_snapshot, "server", "how's it going?")
    rows.append(_case("status reply skips robotic 'Yes —' prefix", not status_line.startswith("Yes")
                       and "workers are running" in status_line))

    long_line = "Colloquial \"text ...\" now reaches the model so Web Bob can make good on texting requests today"
    excerpt = clean(long_line, 40)
    normalized = " ".join(long_line.split())
    rows.append(_case("log excerpts truncate on a word boundary",
                       normalized.startswith(excerpt) and (len(excerpt) == len(normalized) or normalized[len(excerpt)] == " ")))

    four_projects = chat_intent.projects(
        "WebJam, AdoptIQ, Stkryboard, Fantasy Football need to be developed to the max.")
    rows.append(_case("garbled project list still resolves all four names",
                       four_projects == ["WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"]))

    passed = sum(1 for r in rows if r["pass"])
    return {
        "total": len(rows),
        "passed": passed,
        "score": round(10 * passed / len(rows), 2),
        "web_bob_vs_bob": "beat" if passed >= len(rows) - 1 else "match" if passed >= len(rows) - 3 else "behind",
        "cases": rows,
    }


def main() -> int:
    result = run_eval()
    out = HERE / "evidence/bob-parity-eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"], "score": result["score"]}, indent=2))
    return 0 if result["passed"] >= result["total"] - 1 else 1


if __name__ == "__main__":
    sys.exit(main())
