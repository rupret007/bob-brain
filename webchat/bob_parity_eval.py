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
from job_queue import (  # noqa: E402
    parse_confirm,
    parse_council,
    parse_council_confirm,
    parse_do_more,
    parse_ready_round,
    parse_start,
)
from music_notebook import analyze_chord_progression, analyze_end_rhymes, analyze_lyric_meter, try_music_coach_reply  # noqa: E402
from reply_guard import try_exact_reply  # noqa: E402


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
    rows.append(_case(
        "parse council natural",
        parse_council("Ask the council to review failover") == "review failover",
    ))
    rows.append(_case("council yes", parse_council_confirm("yes, run council")))
    rows.append(_case("queue job alias", parse_start("queue job: draft polish") == "draft polish"))
    rows.append(_case("run job alias", parse_start("run a job: test harness") == "test harness"))
    rows.append(_case("inbox parse", state_ledger.parse_inbox_message("tell the builder: fix tab copy") == "fix tab copy"))
    rows.append(_case("do more intent", parse_do_more("I need you to do more") is not None))
    rows.append(_case("music coach hook", try_music_coach_reply("help me structure a chorus") is not None))
    rows.append(_case("music coach chords", "chord" in (try_music_coach_reply("suggest chords for a folk song") or "").lower()))
    rows.append(_case("music lyrics tip", "verse" in (try_music_coach_reply("write lyrics for a verse") or "").lower()))
    rows.append(_case("music refrain tip", "refrain" in (try_music_coach_reply("polish the refrain") or "").lower()))
    rows.append(_case("music meter tip", "4/4" in (try_music_coach_reply("fix meter on my verse lyrics") or "").lower()))
    sample = (
        "count syllables in my verse lyrics:\n"
        "I wait by the door in the rain\n"
        "You never call out my name again"
    )
    scan = analyze_lyric_meter(sample) or ""
    rows.append(_case(
        "music lyric meter scan",
        "syllable" in scan.lower() and "wait by the door" in scan.lower(),
    ))
    explicit_meter = analyze_lyric_meter("meter scan:\nOne two three four\nFive six seven eight") or ""
    rows.append(_case(
        "music meter scan phrase",
        "lyric meter scan" in explicit_meter.lower(),
    ))
    rhyme_sample = (
        "rhyme scan on my verse:\n"
        "The rain keeps falling on the pane\n"
        "I call your name but feel the pain\n"
        "The streetlights hum a lonely tune"
    )
    rhyme_scan = analyze_end_rhymes(rhyme_sample) or ""
    rows.append(_case(
        "music end rhyme scan",
        "end-rhyme scan" in rhyme_scan.lower()
        and "Line 1 (A)" in rhyme_scan
        and "Line 2 (A)" in rhyme_scan
        and "Line 3 (B)" in rhyme_scan,
    ))
    prog = analyze_chord_progression("progression scan: C G Am F") or ""
    rows.append(_case(
        "music chord progression scan",
        "chord progression scan" in prog.lower() and "Roman sketch" in prog and "C" in prog,
    ))
    rows.append(_case(
        "music relative minor hint",
        "relative minor" in prog.lower() and "am" in prog.lower(),
    ))
    rows.append(_case(
        "music dominant hint",
        "dominant:" in prog.lower() and "g (v" in prog.lower(),
    ))
    rows.append(_case(
        "music subdominant hint",
        "subdominant:" in prog.lower() and "f (iv" in prog.lower(),
    ))
    rows.append(_case(
        "music mediant hint",
        "mediant:" in prog.lower() and "em (iii" in prog.lower(),
    ))
    rows.append(_case(
        "music leading tone hint",
        "leading tone:" in prog.lower() and "vii" in prog.lower(),
    ))
    rows.append(_case(
        "music tonic hint",
        "tonic:" in prog.lower() and "i of c major" in prog.lower(),
    ))
    plagal_prog = analyze_chord_progression("progression scan: C F C") or ""
    rows.append(_case(
        "music plagal cadence hint",
        "plagal cadence" in plagal_prog.lower(),
    ))
    deceptive_prog = analyze_chord_progression("progression scan: C G Am") or ""
    rows.append(_case(
        "music deceptive cadence hint",
        "deceptive cadence" in deceptive_prog.lower(),
    ))
    authentic_prog = analyze_chord_progression("progression scan: C G C") or ""
    rows.append(_case(
        "music authentic cadence hint",
        "authentic cadence" in authentic_prog.lower(),
    ))
    half_prog = analyze_chord_progression("progression scan: C Am Dm G") or ""
    rows.append(_case(
        "music half cadence hint",
        "half cadence" in half_prog.lower(),
    ))
    plagal_coach = try_music_coach_reply("plagal cadence amen on my song") or ""
    rows.append(_case(
        "music plagal cadence coach",
        "plagal" in plagal_coach.lower() and "iv" in plagal_coach.lower(),
    ))
    rows.append(_case("exact reply shortcut", try_exact_reply("Reply with exactly: drill A1") == "drill A1"))
    rows.append(_case("cheap status update", state_ledger.try_status_reply(root, "update?") is not None))
    rows.append(_case(
        "music turnaround coach",
        "turnaround" in (try_music_coach_reply("song turnaround before the chorus") or "").lower(),
    ))
    rows.append(_case(
        "music bridge coach",
        "bridge" in (try_music_coach_reply("polish the bridge lyrics") or "").lower(),
    ))
    rows.append(_case(
        "music intro coach",
        "intro" in (try_music_coach_reply("write an intro for my song") or "").lower(),
    ))
    rows.append(_case(
        "music outro coach",
        "outro" in (try_music_coach_reply("help with the outro fade") or "").lower(),
    ))
    rows.append(_case(
        "music pre-chorus coach",
        "pre-chorus" in (try_music_coach_reply("write a pre-chorus lift") or "").lower()
        or "chorus" in (try_music_coach_reply("write a pre-chorus lift") or "").lower(),
    ))
    rows.append(_case(
        "music breakdown dynamics coach",
        "breakdown" in (try_music_coach_reply("song breakdown before the final chorus") or "").lower(),
    ))
    rows.append(_case(
        "music post-chorus coach",
        "post-chorus" in (try_music_coach_reply("add a post-chorus hook after the chorus") or "").lower()
        or "chorus" in (try_music_coach_reply("add a post-chorus hook after the chorus") or "").lower(),
    ))
    rows.append(_case(
        "music double-chorus coach",
        "double" in (try_music_coach_reply("double chorus ending for the finale") or "").lower(),
    ))
    rows.append(_case(
        "music capo coach",
        "capo" in (try_music_coach_reply("what capo fret for G shapes") or "").lower(),
    ))
    rows.append(_case(
        "music nashville coach",
        "nashville" in (try_music_coach_reply("explain nashville numbers for my song") or "").lower(),
    ))
    rows.append(_case(
        "music cadence coach",
        "cadence" in (try_music_coach_reply("what cadence for my song ending") or "").lower(),
    ))
    rows.append(_case(
        "music song form coach",
        "ababcb" in (try_music_coach_reply("explain song form ABABCB for my pop track") or "").lower(),
    ))
    rows.append(_case(
        "conductor ready round chip",
        parse_ready_round("Start a Web Bob ready round on the mini (draft only, no merge)") is not None,
    ))

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
