"""Seven-day comparison records; no prompts, private messages or made-up scores."""
from datetime import date, timedelta
import re

SCENARIOS = ("daily_brief", "current_research", "memory_correction", "draft_approval", "task_followthrough")


def trial_template(start_date, webbob_sha):
    start = date.fromisoformat(start_date)
    if not re.fullmatch(r"[a-f0-9]{40}", webbob_sha):
        raise ValueError("exact Web Bob build required")
    return {"schema": 1, "webbob_sha": webbob_sha, "start_date": start_date, "rows": [
        {"date": (start + timedelta(days=day)).isoformat(), "scenario": scenario, "bot": bot,
         "result": "NOT RUN", "receipt": None, "latency_ms": None, "cost_microdollars": None,
         "jeff_fit": None, "build": webbob_sha if bot == "webbob" else None}
        for day in range(7) for scenario in SCENARIOS for bot in ("grok", "webbob")]}


def record_result(trial, day, scenario, bot, *, result, receipt, latency_ms, cost_microdollars, build):
    if result not in {"PASS", "FAIL", "BLOCKED"} or not isinstance(receipt, str) or not 1 <= len(receipt) <= 200:
        raise ValueError("observed result and evidence reference required")
    if bot == "webbob" and build != trial["webbob_sha"]:
        raise ValueError("build changed; start a new comparison cohort")
    for value in (latency_ms, cost_microdollars):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("unknown metrics stay null; known metrics are nonnegative integers")
    matches = [r for r in trial["rows"] if (r["date"], r["scenario"], r["bot"]) == (day, scenario, bot)]
    if len(matches) != 1 or matches[0]["result"] != "NOT RUN":
        raise ValueError("unknown or already-recorded trial; preserve evidence")
    matches[0].update(result=result, receipt=receipt, latency_ms=latency_ms, cost_microdollars=cost_microdollars, build=build)


def summarize(trial):
    rows = trial["rows"]
    report = {}
    for bot in ("grok", "webbob"):
        selected = [r for r in rows if r["bot"] == bot]
        paired = [r for r in selected if r["result"] in {"PASS", "FAIL"}]
        report[bot] = {"observed": len(paired), "pass": sum(r["result"] == "PASS" for r in paired),
                       "blocked": sum(r["result"] == "BLOCKED" for r in selected),
                       "not_run": sum(r["result"] == "NOT RUN" for r in selected),
                       "unknown_cost_count": sum(r["cost_microdollars"] is None for r in paired)}
    report["replacement_approved"] = False
    report["decision_owner"] = "Jeff"
    return report
