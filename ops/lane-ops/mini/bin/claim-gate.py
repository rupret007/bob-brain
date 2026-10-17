#!/usr/bin/env python3
"""claim-gate: mandatory claim-before-work check for every lane that opens PRs.

Usage:
  claim-gate.py claim  --repo OWNER/R --work-id ID --title T --owner O [--lane L]
                       [--files a,b] [--branch BR] [--pr N] [--ttl-min 180]
  claim-gate.py pre-pr --repo OWNER/R --work-id ID --title T --owner O --branch BR [--files a,b]
  claim-gate.py release --repo OWNER/R --work-id ID --owner O [--status DONE] [--pr URL]
  claim-gate.py release --claim FILE --owner O [--status DONE]      (lane-ops v2: release one exact claim)
  claim-gate.py renew   --claim FILE --owner O                      (lane-ops v2: heartbeat a lease)

Leases (lane-ops v2): `claim --lease-s N` adds heartbeat + lease_s to the claim. A leased claim stops
blocking work N seconds after its last heartbeat even if its TTL is hours away, so a killed lane (screen
quit, kill -9, reboot) frees its work in minutes, not hours. lane-lease.sh renews and releases for you.
Claims without lease_s behave exactly as before.

Exit codes (callers MUST treat anything but 0 as "do not start / do not open a PR"):
  0  CLAIMED / OK_TO_CREATE
  10 SKIP            another open PR or active claim already covers this work
  11 UPDATE_EXISTING fix an existing PR: push to its branch, never open a new PR
  3  BLOCKED         any error (gh down, bad JSON, lock timeout). Fail closed.
"""
import argparse, fcntl, glob, json, os, re, subprocess, sys, time, datetime as dt

ROOT = os.environ.get("CLAIM_GATE_ROOT", "/Users/jeffstory/Documents/bob-overnight-inject")
CLAIMS = os.environ.get("CLAIM_GATE_CLAIMS", os.path.join(ROOT, "coord", "claims"))
GH = os.environ.get("CLAIM_GATE_GH", "gh")
DONE = {"DONE", "RELEASED", "FAILED", "ABANDONED", "HELD"}
STOP = set("a an the and or of to in on for with from by is are be no not when it its this that into as at after before only one all any new add fix make show keep use".split())
TITLE_SIM = 0.6
FILE_SIM = 0.5

def now(): return dt.datetime.now(dt.timezone.utc)
def out(kind, code, **kw):
    print(json.dumps(dict(result=kind, **kw)))
    sys.exit(code)

def toks(t):
    t = re.sub(r"^\s*\[?[A-Z]+[0-9]+\]?[:\s-]+", "", t or "")  # drop item-id prefix like "W03:"
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2}

def jacc(a, b):
    if not a or not b: return 0.0
    return len(a & b) / float(min(len(a), len(b))) if min(len(a), len(b)) >= 3 else len(a & b) / float(len(a | b))

def refnums(t):
    return set(re.findall(r"(?:#|\b(?:pr|iss|issue)[-_ ]?)(\d+)\b", (t or "").lower()))

def title_sim(t1, t2):
    # Different explicit issue/PR numbers => different work, never "similar title".
    n1, n2 = refnums(t1), refnums(t2)
    if n1 and n2 and not (n1 & n2): return 0.0
    return jacc(toks(t1), toks(t2))

def norm_id(s): return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def gh_open_prs(repo):
    r = subprocess.run([GH, "pr", "list", "-R", repo, "--state", "open", "-L", "500",
                        "--json", "number,title,headRefName,files"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0: raise RuntimeError("gh pr list failed: " + r.stderr.strip()[:300])
    prs = json.loads(r.stdout)
    if not isinstance(prs, list): raise RuntimeError("gh pr list: unexpected output")
    return prs

def gh_pr(repo, n):
    r = subprocess.run([GH, "pr", "view", str(n), "-R", repo, "--json", "number,state,headRefName,title"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0: raise RuntimeError("gh pr view failed: " + r.stderr.strip()[:300])
    return json.loads(r.stdout)

def lease_dead(j, at=None):
    """True when a leased claim's heartbeat is older than its lease (legacy claims never lease-expire)."""
    try:
        lease = float(j.get("lease_s") or 0)
    except (TypeError, ValueError):
        return False
    if lease <= 0:
        return False
    try:
        hb = dt.datetime.fromisoformat(j.get("heartbeat") or j.get("created") or "1970-01-01T00:00:00+00:00")
    except (TypeError, ValueError):
        return True
    if hb.tzinfo is None: hb = hb.replace(tzinfo=dt.timezone.utc)
    return ((at or now()) - hb).total_seconds() > lease

def latest_by_key():
    best = {}
    for f in glob.glob(os.path.join(CLAIMS, "*.json")):
        try: j = json.load(open(f))
        except Exception: continue
        k = ((j.get("repo") or "").lower(), norm_id(j.get("work_id") or j.get("task") or ""))
        m = os.path.getmtime(f)
        if k not in best or m >= best[k][0]: best[k] = (m, j, f)
    return best

def live_claims():
    out_ = []
    for (_, _), (_, j, f) in latest_by_key().items():
        try: e = dt.datetime.fromisoformat(j.get("expires", "1970-01-01T00:00:00+00:00"))
        except Exception: continue
        if e.tzinfo is None: e = e.replace(tzinfo=dt.timezone.utc)
        if e < now() or str(j.get("status", "")).upper() in DONE or lease_dead(j): continue
        j["_file"] = f; out_.append(j)
    return out_

def claim_matches(c, a, files):
    repo_short = a.repo.split("/")[-1].lower()
    same_repo = (c.get("repo") or "").lower() == a.repo.lower() or (not c.get("repo") and repo_short in json.dumps(c).lower())
    if not same_repo: return None
    if a.branch and c.get("branch") == a.branch: return None  # this lane's own legacy claim for the same branch
    if a.pr and str(c.get("pr_target") or "") == str(a.pr): return "same PR #%s" % a.pr
    if c.get("work_id") and norm_id(c["work_id"]) == norm_id(a.work_id): return "same work id"
    if title_sim(c.get("title") or c.get("scope") or "", a.title) >= TITLE_SIM: return "similar title"
    cf = set(c.get("files") or [])
    if files and cf and jacc(files, cf) >= FILE_SIM: return "overlapping files"
    return None

def pr_matches(p, a, files):
    if a.branch and p.get("headRefName") == a.branch: return None  # our own PR: handled separately
    if a.work_id and norm_id(a.work_id) in norm_id(p.get("headRefName", "") + " " + p.get("title", "")) and len(norm_id(a.work_id)) >= 4:
        return "work id in open PR"
    if title_sim(p.get("title"), a.title) >= TITLE_SIM: return "similar title"
    pf = {x.get("path") for x in (p.get("files") or []) if isinstance(x, dict)}
    if files and pf and jacc(files, pf) >= FILE_SIM: return "overlapping files"
    return None

class Lock:
    def __enter__(self):
        os.makedirs(CLAIMS, exist_ok=True)
        self.f = open(os.path.join(CLAIMS, ".claim-gate.lock"), "w")
        t0 = time.time()
        while True:
            try: fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB); return self
            except BlockingIOError:
                if time.time() - t0 > 120: raise RuntimeError("claim lock timeout")
                time.sleep(0.5)
    def __exit__(self, *e): fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()

def write_claim(a, status, files, extra=None):
    ts = now().strftime("%Y%m%dT%H%M%S%fZ")
    j = dict(task="gate-%s-%s" % (norm_id(a.repo), norm_id(a.work_id)), repo=a.repo, work_id=a.work_id,
             title=a.title, owner=a.owner, lane=a.lane or a.owner, scope=a.title, branch=a.branch or "",
             files=sorted(files), pr_target=str(a.pr or ""), status=status,
             expires=(now() + dt.timedelta(minutes=a.ttl_min)).isoformat(), next_handoff=a.owner,
             evidence=[], created=now().isoformat())
    if getattr(a, "lease_s", 0):
        j.update(lease_s=int(a.lease_s), heartbeat=now().isoformat())
    if extra: j.update(extra)
    p = os.path.join(CLAIMS, "gate-%s-%s-%s-%s.json" % (norm_id(a.repo.split("/")[-1]), norm_id(a.work_id)[:60], norm_id(a.owner), ts))
    tmp = p + ".tmp"; json.dump(j, open(tmp, "w")); os.rename(tmp, p)
    return p

def cmd_claim(a):
    files = {x for x in (a.files or "").split(",") if x}
    with Lock():
        for c in live_claims():
            if c.get("owner") == a.owner and norm_id(c.get("work_id") or "") == norm_id(a.work_id): continue  # renew own
            why = claim_matches(c, a, files)
            if why: out("SKIP", 10, reason="active claim: " + why, by=c.get("owner"), claim=c.get("_file"), expires=c.get("expires"))
        if a.pr:
            p = gh_pr(a.repo, a.pr)
            if p.get("state") != "OPEN": out("SKIP", 10, reason="PR #%s is %s" % (a.pr, p.get("state")))
            f = write_claim(a, "RUNNING", files, dict(branch=p["headRefName"]))
            out("UPDATE_EXISTING", 11, pr=a.pr, branch=p["headRefName"], claim=f,
                rule="push to this PR's branch; never open a new PR")
        for p in gh_open_prs(a.repo):
            why = pr_matches(p, a, files)
            if why: out("SKIP", 10, reason="open PR: " + why, pr=p["number"], title=p["title"])
            if a.branch and p.get("headRefName") == a.branch:
                f = write_claim(a, "RUNNING", files)
                out("UPDATE_EXISTING", 11, pr=p["number"], branch=a.branch, claim=f)
        f = write_claim(a, "RUNNING", files)
        out("CLAIMED", 0, claim=f)

def cmd_prepr(a):
    files = {x for x in (a.files or "").split(",") if x}
    with Lock():
        mine = [c for c in live_claims() if c.get("owner") == a.owner and (c.get("repo") or "") == a.repo
                and norm_id(c.get("work_id") or "") == norm_id(a.work_id)]
        if not mine: out("BLOCKED", 3, reason="no live claim held by %s for %s; run claim first" % (a.owner, a.work_id))
        for c in live_claims():
            if c in mine or (c.get("owner") == a.owner and norm_id(c.get("work_id") or "") == norm_id(a.work_id)): continue
            why = claim_matches(c, a, files)
            if why: out("SKIP", 10, reason="active claim: " + why, by=c.get("owner"), claim=c.get("_file"))
        for p in gh_open_prs(a.repo):
            if a.branch and p.get("headRefName") == a.branch:
                out("UPDATE_EXISTING", 11, pr=p["number"], branch=a.branch, rule="PR already exists; push only")
            why = pr_matches(p, a, files)
            if why: out("SKIP", 10, reason="open PR: " + why, pr=p["number"], title=p["title"])
        out("OK_TO_CREATE", 0)

def own_claim(a):
    """Load --claim FILE; it must live in CLAIMS and belong to --owner."""
    path = os.path.realpath(a.claim)
    if os.path.dirname(path) != os.path.realpath(CLAIMS) or not path.endswith(".json"):
        out("BLOCKED", 3, reason="claim file is not in the claims folder")
    j = json.load(open(path))
    if j.get("owner") != a.owner: out("BLOCKED", 3, reason="claim belongs to %s, not %s" % (j.get("owner"), a.owner))
    return path, j

def rewrite(path, j):
    tmp = path + ".tmp"; json.dump(j, open(tmp, "w")); os.rename(tmp, path)

def cmd_renew(a):
    with Lock():
        path, j = own_claim(a)
        if str(j.get("status", "")).upper() in DONE: out("BLOCKED", 3, reason="claim already %s" % j.get("status"))
        if lease_dead(j): out("BLOCKED", 3, reason="lease already expired; claim again")
        j["heartbeat"] = now().isoformat()
        rewrite(path, j)
        out("RENEWED", 0, claim=path, heartbeat=j["heartbeat"])

def cmd_release(a):
    if a.claim:
        with Lock():
            path, j = own_claim(a)
            j.update(status=a.status, released=now().isoformat())
            rewrite(path, j)
            out("RELEASED", 0, claim=path)
    if not (a.repo and a.work_id): out("BLOCKED", 3, reason="release needs --claim or --repo and --work-id")
    with Lock():
        f = write_claim(a, a.status, set(), dict(pr=a.pr_url or ""))
        out("RELEASED", 0, claim=f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["claim", "pre-pr", "release", "renew"])
    ap.add_argument("--repo", default=""); ap.add_argument("--work-id", default="")
    ap.add_argument("--claim", default=""); ap.add_argument("--lease-s", type=int, default=0)
    ap.add_argument("--title", default=""); ap.add_argument("--owner", required=True)
    ap.add_argument("--lane", default=""); ap.add_argument("--files", default="")
    ap.add_argument("--branch", default=""); ap.add_argument("--pr", default="")
    ap.add_argument("--pr-url", default=""); ap.add_argument("--status", default="DONE")
    ap.add_argument("--ttl-min", type=int, default=180)
    a = ap.parse_args()
    if a.cmd == "renew" or (a.cmd == "release" and a.claim):
        if not a.claim: out("BLOCKED", 3, reason="--claim required")
        {"renew": cmd_renew, "release": cmd_release}[a.cmd](a)
    if not a.repo or not a.work_id: out("BLOCKED", 3, reason="--repo and --work-id required")
    if a.cmd != "release" and not a.title and not a.pr: out("BLOCKED", 3, reason="--title or --pr required")
    if "/" not in a.repo: out("BLOCKED", 3, reason="--repo must be OWNER/NAME")
    {"claim": cmd_claim, "pre-pr": cmd_prepr, "release": cmd_release}[a.cmd](a)

if __name__ == "__main__":
    try: main()
    except SystemExit: raise
    except BaseException as e:  # fail closed
        print(json.dumps(dict(result="BLOCKED", reason="%s: %s" % (type(e).__name__, e))))
        sys.exit(3)
