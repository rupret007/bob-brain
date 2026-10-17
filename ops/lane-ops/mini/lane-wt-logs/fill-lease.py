#!/usr/bin/env python3
"""Before lane-fill starts a job: skip if Lane Dispatcher holds the repo/PR; else take a claim-gate lease."""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

GATE = os.environ.get(
    "CLAIM_GATE",
    "/Users/jeffstory/Documents/bob-overnight-inject/bin/claim-gate.py",
)
CLAIMS = os.environ.get(
    "CLAIM_GATE_CLAIMS",
    "/Users/jeffstory/Documents/bob-overnight-inject/coord/claims",
)
OWNER = "lane-fill"
LANE = "lane-fill"
DONE = {"DONE", "RELEASED", "FAILED", "ABANDONED", "HELD"}


SKIP_STATE = os.environ.get(
    "FILL_SKIP_STATE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fill-skip-state.json"),
)
SKIP_LIMIT = int(os.environ.get("FILL_SKIP_LIMIT", "20"))


def _load_skips():
    try:
        return json.load(open(SKIP_STATE))
    except Exception:
        return {}


def _save_skips(state):
    tmp = SKIP_STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, SKIP_STATE)


def parked_until(job):
    """ISO expires if job parked after SKIP_LIMIT skips and claim not expired, else None."""
    state = _load_skips()
    e = state.get(job) or {}
    count = int(e.get("count") or 0)
    exp = e.get("parked_until") or e.get("expires")
    if count < SKIP_LIMIT or not exp:
        return None
    try:
        ed = dt.datetime.fromisoformat(exp)
    except Exception:
        return None
    if ed.tzinfo is None:
        ed = ed.replace(tzinfo=dt.timezone.utc)
    if ed < now():
        state.pop(job, None)
        _save_skips(state)
        return None
    return exp


def note_skip(job, expires=None):
    """Count a SKIP; park the job once count >= SKIP_LIMIT until claim expires."""
    state = _load_skips()
    e = dict(state.get(job) or {})
    e["count"] = int(e.get("count") or 0) + 1
    if expires:
        e["expires"] = expires
        if e["count"] >= SKIP_LIMIT:
            e["parked_until"] = expires
    e["last"] = now().isoformat()
    state[job] = e
    _save_skips(state)
    return e


def expires_from_out(out):
    try:
        j = json.loads((out or "").strip().splitlines()[-1])
        return j.get("expires")
    except Exception:
        return None



def now():
    return dt.datetime.now(dt.timezone.utc)


def live_claims():
    out = []
    best = {}
    for f in glob.glob(os.path.join(CLAIMS, "*.json")):
        try:
            j = json.load(open(f))
        except Exception:
            continue
        k = ((j.get("repo") or "").lower(), (j.get("work_id") or j.get("task") or "").lower())
        m = os.path.getmtime(f)
        if k not in best or m >= best[k][0]:
            best[k] = (m, j, f)
    for _, j, f in best.values():
        try:
            e = dt.datetime.fromisoformat(j.get("expires", "1970-01-01T00:00:00+00:00"))
        except Exception:
            continue
        if e.tzinfo is None:
            e = e.replace(tzinfo=dt.timezone.utc)
        if e < now() or str(j.get("status", "")).upper() in DONE:
            continue
        j = dict(j)
        j["_file"] = f
        out.append(j)
    return out


def parse_prompt(text):
    repos = []
    seen = set()
    for r in re.findall(r"rupret007/[A-Za-z0-9._-]+", text):
        r = r.rstrip(".,;:)")
        if r.lower() not in seen:
            seen.add(r.lower())
            repos.append(r)
    # Drop negated PR mentions ("not already covered by PR #70", "except PR #N")
    cleaned = re.sub(
        r"(?i)(?:not\s+(?:already\s+)?covered\s+by|except|excluding|other\s+than|avoid)\s+PR\s*#?\d+",
        " ",
        text,
    )
    prs = set()
    for a, b in re.findall(r"#(\d+)\s*[-–]\s*#?(\d+)", cleaned):
        lo, hi = int(a), int(b)
        if lo > hi:
            lo, hi = hi, lo
        for n in range(lo, hi + 1):
            prs.add(n)
    # Prefer explicit targets: "PR #N", "draft PR #N", "PRs #N,#M"
    for n in re.findall(r"(?i)(?:draft\s+)?PR[s]?\s*#?(\d+)", cleaned):
        prs.add(int(n))
    # Also bare "#N" next to branch/work cues, but only if we already saw a PR keyword elsewhere
    if re.search(r"(?i)\bPR[s]?\b", cleaned):
        for n in re.findall(r"#(\d+)", cleaned):
            prs.add(int(n))
    return repos, sorted(prs)


def lane_holds(repo, prs):
    """Skip if Lane Dispatcher has any live claim on this repo (or matching PR)."""
    for c in live_claims():
        if (c.get("owner") or "") != "lane-dispatcher":
            continue
        if (c.get("repo") or "").lower() != repo.lower():
            continue
        # Whole-repo hold: Lane owns work on this repo until lease expires.
        return c
    return None


def claim_repo(repo, work_id, title, pr=None):
    args = [
        sys.executable,
        GATE,
        "claim",
        "--repo",
        repo,
        "--work-id",
        work_id,
        "--title",
        title,
        "--owner",
        OWNER,
        "--lane",
        LANE,
        "--ttl-min",
        "300",
    ]
    if pr is not None:
        args += ["--pr", str(pr)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=180)
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode, out


def main():
    args = [a for a in sys.argv[1:] if a != "--check-only"]
    check_only = "--check-only" in sys.argv[1:]
    if len(args) < 2:
        print(json.dumps({"result": "BLOCKED", "reason": "usage: fill-lease.py [--check-only] JOB PROMPT"}))
        return 3
    job, pf = args[0], args[1]
    try:
        text = open(pf).read()
    except OSError as e:
        print(json.dumps({"result": "BLOCKED", "reason": "prompt unreadable: %s" % e}))
        return 3
    pu = parked_until(job)
    if pu:
        print(json.dumps({
            "result": "SKIP",
            "reason": "parked after %d skips until claim expires" % SKIP_LIMIT,
            "job": job,
            "expires": pu,
        }))
        return 1
    repos, prs = parse_prompt(text)
    # Issue jobs (job id ...-issN or ISSUE_JOB marker): never a PR lease. Claim via the issue.
    m_iss = re.search(r"-iss(\d+)$", job) or re.search(r"ISSUE_JOB issue=#(\d+)", text)
    if m_iss:
        issue_n = int(m_iss.group(1))
        if not repos:
            print(json.dumps({"result": "BLOCKED", "reason": "no rupret007 repo in prompt", "job": job}))
            return 3
        held = lane_holds(repos[0], [])
        if held:
            note_skip(job, held.get("expires"))
            print(json.dumps({"result": "SKIP", "reason": "lane-dispatcher holds repo", "job": job,
                              "repo": repos[0], "issue": issue_n, "work_id": held.get("work_id"),
                              "expires": held.get("expires")}))
            return 1
        if check_only:
            print(json.dumps({"result": "WOULD_CLAIM", "kind": "issue", "job": job, "repos": repos[:1],
                              "issue": issue_n, "owner": OWNER}))
            return 0
        args2 = [sys.executable, GATE, "claim", "--repo", repos[0], "--work-id", "issue-%d" % issue_n,
                 "--title", "lane-fill implement issue #%d then open draft PR (%s)" % (issue_n, job),
                 "--owner", OWNER, "--lane", LANE, "--branch", "lane/auto-issue-%d" % issue_n,
                 "--ttl-min", "300"]
        r = subprocess.run(args2, capture_output=True, text=True, timeout=180)
        out = (r.stdout or r.stderr or "").strip()
        print(out)
        if r.returncode not in (0, 11):
            note_skip(job, expires_from_out(out))
            return 1 if r.returncode == 10 else 3
        return 0
    if not repos:
        print(json.dumps({"result": "BLOCKED", "reason": "no rupret007 repo in prompt", "job": job}))
        return 3
    for repo in repos:
        held = lane_holds(repo, prs)
        if held:
            note_skip(job, held.get("expires"))
            print(
                json.dumps(
                    {
                        "result": "SKIP",
                        "reason": "lane-dispatcher holds repo",
                        "job": job,
                        "repo": repo,
                        "by": held.get("owner"),
                        "work_id": held.get("work_id"),
                        "pr": held.get("pr_target"),
                        "expires": held.get("expires"),
                        "claim": held.get("_file"),
                    }
                )
            )
            return 1
    if check_only:
        print(json.dumps({"result": "WOULD_CLAIM", "job": job, "repos": repos, "prs": prs, "owner": OWNER}))
        return 0
    work_id = "fill-%s" % job
    title = "lane-fill queue job %s" % job
    # Single-PR jobs: claim with --pr (UPDATE_EXISTING=11 is go). Multi-PR / no-PR: claim without --pr.
    primary_pr = prs[0] if len(prs) == 1 else None
    rc, out = claim_repo(repos[0], work_id, title, primary_pr)
    print(out)
    if rc not in (0, 11):
        note_skip(job, expires_from_out(out))
        return 1 if rc == 10 else 3
    for repo in repos[1:]:
        rc2, out2 = claim_repo(repo, work_id, title, None)
        print(out2)
        if rc2 == 10:
            note_skip(job, expires_from_out(out2))
            return 1
        if rc2 not in (0, 11):
            return 3
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        print(json.dumps({"result": "BLOCKED", "reason": "%s: %s" % (type(e).__name__, e)}))
        sys.exit(3)
