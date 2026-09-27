#!/usr/bin/env python3
"""Reply-quality eval suite for Web Bob (offline by default; optional --live)."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from build_info import BUILD
from reply_builder import build_reply
from reply_rubric import evaluate_rubrics

HERE = Path(__file__).resolve().parent
CODE_ROOT = HERE.parent
CASES_PATH = HERE / "reply_eval_cases.json"


def load_cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def run_offline(code_root: Path, cases: list[dict]) -> list[dict]:
    rows = []
    eval_root = code_root / ".reply-eval-runtime"
    for case in cases:
        outcome = build_reply(
            case["prompt"],
            code_root=code_root,
            fixture=case.get("fixture"),
            stub_model=case.get("stub_model"),
        )
        rubric_rows = evaluate_rubrics(
            outcome.content,
            eval_root,
            case.get("rubrics", []),
            outcome.as_meta(),
        )
        rows.append(dict(
            id=case["id"],
            category=case["category"],
            session=case.get("session"),
            prompt=case["prompt"],
            provider=outcome.provider,
            reply_preview=outcome.content[:240],
            rubrics=rubric_rows,
            passed=all(row["ok"] for row in rubric_rows),
        ))
    return rows


def run_live(url: str, password_file: Path, cases: list[dict]) -> list[dict]:
    import http.cookiejar
    import urllib.parse
    import urllib.request

    from reply_rubric import evaluate_rubrics

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    origin = url.rstrip("/")

    def call(route, payload=None, csrf=None):
        headers = {"Origin": origin}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": csrf or ""})
        request = urllib.request.Request(
            origin + route,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        with opener.open(request, timeout=30) as response:
            return json.load(response)

    login = urllib.request.Request(
        origin + "/login",
        data=urllib.parse.urlencode({"password": password_file.read_text().strip()}).encode(),
        headers={"Origin": origin},
    )
    opener.open(login)
    csrf = call("/api/session")["csrf"]
    conversation_id = call("/api/conversations", {}, csrf=csrf)["id"]
    rows = []
    for case in cases:
        request_id = str(uuid.uuid4())
        before_jobs = 0
        value = call("/api/messages", dict(
            conversation_id=conversation_id,
            message=case["prompt"],
            request_id=request_id,
        ), csrf=csrf)
        deadline = time.monotonic() + 45
        while True:
            answer = next(
                (m for m in value["messages"]
                 if m.get("request_id") == request_id and m["role"] == "assistant"),
                None,
            )
            if answer and answer.get("status") == "done":
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"live reply timed out for {case['id']}")
            time.sleep(0.2)
            value = call(f"/api/conversations/{conversation_id}", csrf=csrf)
        content = answer.get("content") or ""
        meta = dict(
            task_ids=answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else []),
            jobs_created=before_jobs,
            action_queued=bool(answer.get("action_card")),
            provider=answer.get("provider"),
        )
        rubric_rows = evaluate_rubrics(content, CODE_ROOT, case.get("rubrics", []), meta)
        rows.append(dict(
            id=case["id"],
            category=case["category"],
            session=case.get("session"),
            prompt=case["prompt"],
            provider=answer.get("provider"),
            reply_preview=content[:240],
            rubrics=rubric_rows,
            passed=all(row["ok"] for row in rubric_rows),
        ))
    return rows


def render_markdown(payload: dict, rows: list[dict], mode: str) -> str:
    passed = sum(1 for row in rows if row["passed"])
    lines = [
        "# Web Bob reply-quality eval (0927)",
        "",
        f"- Baseline: `{payload.get('baseline_sha', BUILD['short_sha'])}`",
        f"- Mode: **{mode}**",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Score: **{passed}/{len(rows)}** prompts passing all rubrics",
        "",
        "| ID | Category | Pass | Provider | Failed rubrics |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        failed = [f"{r['rubric']}: {r['detail']}" for r in row["rubrics"] if not r["ok"]]
        lines.append(
            f"| {row['id']} | {row['category']} | {'PASS' if row['passed'] else 'FAIL'} | "
            f"{row.get('provider') or '—'} | {'; '.join(failed) or '—'} |"
        )
    lines.extend(["", "## Per-prompt detail", ""])
    for row in rows:
        lines.append(f"### {row['id']} ({row['category']}) — {'PASS' if row['passed'] else 'FAIL'}")
        lines.append(f"- Session: `{row.get('session', '—')}`")
        lines.append(f"- Prompt: {row['prompt']}")
        lines.append(f"- Preview: {row['reply_preview']}")
        for rubric in row["rubrics"]:
            mark = "ok" if rubric["ok"] else "FAIL"
            detail = f" ({rubric['detail']})" if rubric["detail"] else ""
            lines.append(f"- `{rubric['rubric']}`: {mark}{detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Hit a running Web Bob server (authenticated).")
    parser.add_argument("--url", default=os.environ.get("WEBBOB_URL", "https://jeffs-mac-mini.tail758ab4.ts.net"))
    parser.add_argument("--password-file", type=Path, default=CODE_ROOT / "conductor/webchat/.password")
    parser.add_argument("--report", type=Path, default=CODE_ROOT / "reviews/WEBBOB-EVALS-0927.md")
    parser.add_argument("--json-out", type=Path, default=CODE_ROOT / "reviews/WEBBOB-EVALS-0927.json")
    args = parser.parse_args()

    payload = load_cases()
    cases = payload["cases"]
    if args.live:
        if not args.password_file.is_file():
            raise SystemExit("password file missing for --live (path not printed).")
        rows = run_live(args.url.rstrip("/"), args.password_file, cases)
        mode = f"live ({args.url})"
    else:
        rows = run_offline(CODE_ROOT, cases)
        mode = "offline (reply_builder)"

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(dict(mode=mode, baseline=payload.get("baseline_sha"), rows=rows), indent=2) + "\n")
    args.report.write_text(render_markdown(payload, rows, mode))
    print(f"Wrote {args.report} ({sum(1 for r in rows if r['passed'])}/{len(rows)} pass)")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
