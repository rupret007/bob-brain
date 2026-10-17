#!/usr/bin/env python3
"""Refill lane-wt fill.queue from open draft PRs and issues (priority order).

Called by fill.sh when the queue is low. Skips repos/PRs held by Lane Dispatcher
(via fill-lease --check-only). Never merges. Writes q-<job>.prompt + appends job ids.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

LOGS = os.path.expanduser("~/lane-wt/logs")
QUEUE = os.path.join(LOGS, "fill.queue")
LEASE = os.path.join(LOGS, "fill-lease.py")
DISPATCH = os.path.join(LOGS, "dispatch.log")
GH = os.environ.get("GH", "gh")
# lane-ops v2: only work authored by these logins becomes a lane prompt. Several repos are PUBLIC, and lane prompts
# embed PR/issue titles and tell agents to read PR comments, so a stranger's PR or issue must never start a lane.
TRUSTED_AUTHORS = {a.strip().lower() for a in os.environ.get("LANE_TRUSTED_AUTHORS", "rupret007").split(",") if a.strip()}

# Jeff priority: Web Bob, WebJam, AdoptIQ, StoryBoard, then band sites / rest.
PRIORITY = [
    ("bob-brain", "rupret007/bob-brain"),
    ("StalemateSite", "rupret007/StalemateSite"),   # v6 Jeff order: Web Bob, Stalemate, games, Hang Out, rest
    ("Turdanoid", "rupret007/Turdanoid"),
    ("webjam", "rupret007/webjam"),
    ("AdoptIQ", "rupret007/AdoptIQ"),
    ("StoryBoard", "rupret007/StoryBoard"),
    ("rad-dad-show-night", "rupret007/rad-dad-show-night"),
    ("RadDadSite", "rupret007/RadDadSite"),
    ("AI-Music-Vault", "rupret007/AI-Music-Vault"),
    ("TrailerParkDerby", "rupret007/TrailerParkDerby"),
    ("storyland-draft-and-season", "rupret007/storyland-draft-and-season"),
    ("Storyland-Fantasy-Football", "rupret007/Storyland-Fantasy-Football"),
    ("StoryDesk", "rupret007/StoryDesk"),
    ("Andrea_NanoBot", "rupret007/Andrea_NanoBot"),
]

LOW_WATER = int(os.environ.get("FILL_LOW_WATER", "2"))
TARGET = int(os.environ.get("FILL_REFILL_TARGET", "6"))
MAX_PER_REPO = int(os.environ.get("FILL_MAX_PER_REPO", "2"))
RULES = (
    "RULES: draft PRs only; never merge, force-push, tag, release or deploy; "
    "never loosen/skip/delete tests; no secrets; prepaid/$0 only; no external messages; "
    "do not touch ~/.cursor, Keychain, svc-* screens, Codex/Claude auth, personal music, chat.db. "
    "HEAVY TESTS: if ~/bin/nuc-verify exists (Mac mini), run Node/Playwright/vitest gates from your worktree via "
    "`~/bin/nuc-verify -- bash -c '<test cmd>'` so they run on the NucBox; keep macOS-only tests and WebKit play.spec.js local; "
    "on the NucBox just run tests normally. "
    "End by printing exactly: RESULT branch=<b> pr=<url> head=<sha> tests=<summary>  (or BLOCKER <reason>)."
)


SKIP_STATE = os.environ.get(
    "FILL_SKIP_STATE",
    os.path.join(LOGS, "fill-skip-state.json"),
)
SKIP_LIMIT = int(os.environ.get("FILL_SKIP_LIMIT", "20"))


def is_parked(job: str) -> bool:
    """True if fill-lease parked this job after SKIP_LIMIT skips (claim not expired)."""
    try:
        state = json.load(open(SKIP_STATE))
    except Exception:
        return False
    e = state.get(job) or {}
    if int(e.get("count") or 0) < SKIP_LIMIT:
        return False
    exp = e.get("parked_until") or e.get("expires")
    if not exp:
        return False
    try:
        ed = datetime.fromisoformat(exp)
    except Exception:
        return False
    if ed.tzinfo is None:
        ed = ed.replace(tzinfo=timezone.utc)
    if ed < datetime.now(timezone.utc):
        return False
    return True



def log(msg: str) -> None:
    line = f"{datetime.now().astimezone():%a %b %d %H:%M:%S %Z %Y} fill-autoqueue {msg}"
    print(line)
    try:
        with open(DISPATCH, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run(cmd, timeout=90):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def trusted(item: dict) -> bool:
    """True only for same-repo PRs/issues opened by a trusted author (fail closed on missing fields)."""
    author = ((item.get("author") or {}).get("login") or "").lower()
    if author not in TRUSTED_AUTHORS:
        return False
    if item.get("isCrossRepository") is True:
        return False
    return True


def read_queue() -> list[str]:
    if not os.path.isfile(QUEUE):
        return []
    return [t for t in open(QUEUE).read().split() if t]


def classify(text: str) -> str:
    """v5 routing: tag tier/provider for fill.sh (see lane-route.conf)."""
    # grok 10/16 18:52: classify the TASK only; the shared RULES boilerplate ("no secrets", "Codex/Claude auth",
    # "tests") made every job xhigh->Codex on the Mini and starved the NucBox cursor lanes.
    t = re.sub(r"RULES:.*?(?=End by printing|$)", " ", text.replace(RULES, " "), flags=re.S).lower()
    if any(k in t for k in ("security", "auth", "oauth", "secret", "karen fail", "gate fail", "nats", "cap ", "spend", "race", "deadlock")):
        tier, prov = ("xhigh" if any(k in t for k in ("security", "auth", "oauth", "secret")) else "high"), "codex"
    elif any(k in t for k in ("screenshot", "visual", "playwright", "browser")):
        tier, prov = "cheap", "cursor"   # needs a real browser on the NucBox
    elif any(k in t for k in ("critique", "honesty", "review only", "typo", "copy change", "docs", "readme", "test-only", "add tests", "coverage")):
        tier, prov = "cheap", "gemini"   # v6 21:58 CT 10/16: Gemini default routine lane
    elif "hard review" in t:
        tier, prov = "high", "claude"
    else:
        tier, prov = "cheap", "gemini"   # v6: routine fixes -> Gemini (code mode, tests on NucBox, cursor fallback)
    return f"tier={tier}\nprovider={prov}\n"

def write_queue(jobs: list[str]) -> None:
    # preserve order, unique
    seen = set()
    out = []
    for j in jobs:
        if j not in seen:
            seen.add(j)
            out.append(j)
    with open(QUEUE, "w") as f:
        f.write(" ".join(out) + ("\n" if out else ""))


def active_lane_jobs() -> set[str]:
    r = run(["screen", "-ls"])
    found = set()
    # lane-ops v2: fill.sh v5+ names screens lane-<provider>-<job>; matching only lane-q- missed every running job
    for m in re.finditer(r"\.lane-(?:q|codex-nuc|codex|cursor|gemini|claude|minimax)-([A-Za-z0-9._-]+)", r.stdout + r.stderr):
        found.add(m.group(1))
    return found


def lease_ok(job: str, prompt_path: str) -> bool:
    r = run([sys.executable, LEASE, "--check-only", job, prompt_path], timeout=60)
    if r.returncode != 0:
        return False
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return False
    return j.get("result") in ("WOULD_CLAIM", "CLAIMED", "OK")


def gh_json(args: list[str]):
    try:
        r = run([GH, *args], timeout=120)
    except (subprocess.TimeoutExpired, OSError) as e:  # lane-ops v2: one hung gh call used to abort the whole refill
        log(f"gh failed ({type(e).__name__}) for {' '.join(args[:4])}")
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return None


def list_draft_prs(repo: str) -> list[dict]:
    data = gh_json(
        [
            "pr",
            "list",
            "-R",
            repo,
            "--state",
            "open",
            "--limit",
            "30",
            "--json",
            "number,title,isDraft,updatedAt,mergeable,url,headRefName,author,isCrossRepository",
        ]
    )
    if not data:
        return []
    # Prefer drafts; also include non-draft open if marked PRE_KAREN / needs work in title
    out = []
    for p in data:
        if not trusted(p):
            log(f"skip untrusted PR {repo}#{p.get('number')} (author={((p.get('author') or {}).get('login'))!r}, cross={p.get('isCrossRepository')})")
            continue
        title = p.get("title") or ""
        if p.get("isDraft") or re.search(r"PRE_KAREN|DO NOT MERGE|HELD|DRAFT", title, re.I):
            out.append(p)
    return out


def list_issues(repo: str) -> list[dict]:
    data = gh_json(
        [
            "issue",
            "list",
            "-R",
            repo,
            "--state",
            "open",
            "--limit",
            "15",
            "--json",
            "number,title,updatedAt,url,author",
        ]
    )
    out = []
    for i in data or []:
        if trusted(i):
            out.append(i)
        else:
            log(f"skip untrusted issue {repo}#{i.get('number')} (author={((i.get('author') or {}).get('login'))!r})")
    return out


def issue_has_open_pr(repo: str, n: int):
    """Return an open PR number that already references issue #n, else None."""
    data = gh_json(["pr", "list", "-R", repo, "--state", "open", "--limit", "50",
                    "--search", f"{n} in:title,body", "--json", "number,title,body"])
    for p in data or []:
        if re.search(rf"#{n}\b", (p.get("title") or "") + " " + (p.get("body") or "")):
            return p["number"]
    return None


def job_id(short: str, kind: str, num: int) -> str:
    # screen session name limit-friendly
    j = f"auto-{short}-{kind}{num}"
    return re.sub(r"[^A-Za-z0-9._-]", "-", j)[:48]


def prompt_for_pr(repo: str, pr: dict) -> str:
    n = pr["number"]
    title = (pr.get("title") or "").replace("\n", " ")[:120]
    branch = pr.get("headRefName") or ""
    return (
        f"Repo {repo}, draft/open PR #{n} ({title}). "
        f"git fetch origin && git checkout the PR branch"
        + (f" ({branch})" if branch else "")
        + ". Read PR comments and CI; fix REAL must-fixes, conflicts, and failing checks with regression tests; "
        "push normal commits (no force); comment a short numbered status. Do not merge. Do not open a duplicate PR. "
        f"{RULES}"
    )


def prompt_for_issue(repo: str, issue: dict) -> str:
    n = issue["number"]
    title = (issue.get("title") or "").replace("\n", " ")[:120]
    short = repo.split("/")[-1]
    return (
        f"ISSUE_JOB issue=#{n} kind=implement-issue-then-draft-pr. "
        f"Repo {repo}, open issue #{n} ({title}). "
        f"git fetch && git checkout -B lane/auto-issue-{n} origin/HEAD. "
        "Implement the highest-value slice of this issue with tests; open a DRAFT PR linking the issue "
        "(or push onto an existing covering draft — never duplicate). Do not merge. "
        f"{RULES}"
    )


def main() -> int:
    q = read_queue()
    active = active_lane_jobs()
    pending = [j for j in q if j not in active]
    # Drop jobs whose screens already finished from the front conceptually — keep file as remaining+new
    if len(pending) >= LOW_WATER:
        log(f"skip refill: pending={len(pending)} (>= low-water {LOW_WATER}) queue={pending}")
        return 0

    need = max(0, TARGET - len(pending))
    log(f"refill start: pending={len(pending)} need={need} active={sorted(active)}")
    added: list[str] = []
    per_repo: dict[str, int] = {}

    for short, repo in PRIORITY:
        if len(added) >= need:
            break
        per_repo.setdefault(repo, 0)
        # Draft PRs first (higher value than bare issues)
        for pr in list_draft_prs(repo):
            if len(added) >= need or per_repo[repo] >= MAX_PER_REPO:
                break
            n = pr["number"]
            jid = job_id(short, "pr", n)
            if jid in pending or jid in active or jid in added or jid in q:
                continue
            # Skip if any existing prompt (hand or queued) already targets this PR
            skip = False
            for pp in glob.glob(os.path.join(LOGS, "q-*.prompt")):
                try:
                    body = open(pp).read()
                except OSError:
                    continue
                # grok 10/16 18:46: match "PR #n" only; bare "#n" mentions in stack prompts starved the queue
                if repo in body and re.search(rf"\bPR\s*#{n}\b", body):
                    skip = True
                    break
            if skip:
                log(f"skip {jid}: existing prompt already targets PR #{n}")
                continue
            if is_parked(jid):
                log(f"skip {jid} (parked until blocking claim expires)")
                continue
            prompt = prompt_for_pr(repo, pr)
            path = os.path.join(LOGS, f"q-{jid}.prompt")
            with open(path, "w") as f:
                f.write(prompt + "\n")
            with open(path[:-len(".prompt")] + ".lane", "w") as lf:
                lf.write(classify(prompt))
            if not lease_ok(jid, path):
                log(f"skip {jid} (lease blocked)")
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue
            added.append(jid)
            per_repo[repo] += 1
            log(f"queued {jid} from {repo} PR #{n}")

        # grok 10/16 18:48: Jeff 10/14 WebJam closeout rule - no NEW PRs (issue jobs) while >=10 WebJam PRs are open
        if repo == "rupret007/webjam":
            _open = gh_json(["pr", "list", "-R", repo, "--state", "open", "--limit", "300", "--json", "number"])
            if _open is None or len(_open) >= 10:
                log(f"skip webjam issue jobs: closeout rule ({'unknown' if _open is None else len(_open)} open PRs >= 10)")
                continue
        for issue in list_issues(repo):
            if len(added) >= need or per_repo[repo] >= MAX_PER_REPO:
                break
            n = issue["number"]
            jid = job_id(short, "iss", n)
            if jid in pending or jid in active or jid in added or jid in q:
                continue
            covering = issue_has_open_pr(repo, n)
            if covering:
                log(f"skip {jid}: issue #{n} already covered by open PR #{covering} (issue job, no PR lease)")
                continue
            if is_parked(jid):
                log(f"skip {jid} (parked until blocking claim expires)")
                continue
            prompt = prompt_for_issue(repo, issue)
            path = os.path.join(LOGS, f"q-{jid}.prompt")
            with open(path, "w") as f:
                f.write(prompt + "\n")
            with open(path[:-len(".prompt")] + ".lane", "w") as lf:
                lf.write(classify(prompt))
            if not lease_ok(jid, path):
                log(f"skip {jid} (lease blocked)")
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue
            added.append(jid)
            per_repo[repo] += 1
            log(f"queued {jid} from {repo} issue #{n} as implement-issue-then-draft-PR job (issue claim, not PR lease)")

    new_q = pending + added
    write_queue(new_q)
    log(f"refill done: added={len(added)} queue={new_q}")
    print(json.dumps({"added": added, "queue": new_q, "pending_before": pending}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        log(f"ERROR {e!r}")
        raise
