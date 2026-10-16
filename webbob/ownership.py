#!/usr/bin/env python3
"""Staged claim gate: local coordination lock and append-only JSON, plus fencing.

Reuses the existing conductor gate's lock, file format and PR duplicate checks.
CLI: claim/pre-pr/renew/release/get-owner; see --help. Exit 0 means success,
3 means BLOCKED (including UPDATE_EXISTING); callers must stop on nonzero.
Identity is trusted launcher configuration; model arguments never select it.
"""
import argparse, fcntl, json, os, re, subprocess, sys, time, datetime as dt
import contextlib, hashlib, secrets
from pathlib import Path

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

class GateError(RuntimeError):
    """Unknown state and authorization failures always deny execution."""


def read_records():
    # iterdir, unlike glob, does not turn an unreadable directory into no claims.
    records = []
    for path in sorted(Path(CLAIMS).iterdir()):
        if path.suffix != ".json":
            continue
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise GateError("unsafe claim record")
        try:
            j = json.loads(path.read_text())
            if not isinstance(j, dict):
                raise ValueError()
            for key in ("owner", "status", "expires"):
                if not isinstance(j.get(key), str) or not j[key]:
                    raise ValueError()
            identity = j.get("work_id") or j.get("task")
            if not isinstance(identity, str) or not norm_id(identity):
                raise ValueError()
            if not isinstance(j.get("repo"), str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", j["repo"]):
                raise ValueError()
            expiry = dt.datetime.fromisoformat(j["expires"])
            if expiry.tzinfo is None:
                raise ValueError()
            if "created" in j and dt.datetime.fromisoformat(j["created"]).tzinfo is None:
                raise ValueError()
            if j.get("status").upper() not in DONE | {"RUNNING", "CLAIMED", "ACTIVE"}:
                raise ValueError()
            if not isinstance(j.get("files", []), list):
                raise ValueError()
            for filename in j.get("files", []):
                if not isinstance(filename, str) or not filename or filename.startswith("/"):
                    raise ValueError()
                canonical("repo:" + j["repo"] + "/" + filename)
            if "sequence" not in j and any(k in j for k in ("resources", "fence", "token_hash")):
                raise ValueError()
            # New records require explicit ordering; never use filesystem mtime.
            if "sequence" in j:
                if type(j["sequence"]) is not int or j["sequence"] < 1:
                    raise ValueError()
                if not isinstance(j.get("resources"), list) or not j["resources"]:
                    raise ValueError()
                for resource in j["resources"]:
                    if canonical(resource) != resource:
                        raise ValueError()
                if type(j.get("fence")) is not int or not 0 < j["fence"] <= j["sequence"]:
                    raise ValueError()
                if not re.fullmatch(r"[a-f0-9]{64}", j.get("token_hash", "")):
                    raise ValueError()
            j["_file"] = str(path)
            records.append(j)
        except (ValueError, TypeError, KeyError) as exc:
            raise GateError("malformed claim record: " + path.name) from exc
    sequences = [j["sequence"] for j in records if "sequence" in j]
    if len(sequences) != len(set(sequences)):
        raise GateError("duplicate claim sequence")
    return records


def latest_by_key(records=None):
    records = read_records() if records is None else records
    migrated = {}
    for j in records:
        if "sequence" in j:
            key = (j["repo"].lower(), norm_id(j.get("work_id") or j["task"]))
            stamp = dt.datetime.fromisoformat(j["created"])
            migrated[key] = min(migrated.get(key, stamp), stamp)
    best = {}
    for j in records:
        k = ((j.get("repo") or "").lower(), norm_id(j.get("work_id") or j["task"]))
        # Legacy records use their written timestamps, not mutable file metadata.
        stamp = dt.datetime.fromisoformat(j.get("created") or j["expires"])
        if "sequence" not in j and k in migrated and stamp >= migrated[k]:
            raise GateError("legacy writer changed a migrated claim")
        order = (j.get("sequence", 0), stamp)
        if k in best and order == best[k][0]:
            raise GateError("ambiguous claim history")
        if k not in best or order > best[k][0]:
            best[k] = (order, j, j["_file"])
    return best


def live_claims(records=None):
    return [j for _, j, _ in latest_by_key(records).values()
            if dt.datetime.fromisoformat(j["expires"]) > now()
            and j["status"].upper() not in DONE]


def claim_matches(c, a, files):
    repo_short = a.repo.split("/")[-1].lower()
    same_repo = (c.get("repo") or "").lower() == a.repo.lower() or (not c.get("repo") and repo_short in json.dumps(c).lower())
    if not same_repo: return None
    if a.branch and c.get("branch") == a.branch and c.get("owner") == a.owner and norm_id(c.get("work_id", "")) == norm_id(a.work_id): return None  # this lane's own legacy claim for the same branch
    if a.pr and str(c.get("pr_target") or "") == str(a.pr): return "same PR #%s" % a.pr
    if c.get("work_id") and norm_id(c["work_id"]) == norm_id(a.work_id): return "same work id"
    if jacc(toks(c.get("title") or c.get("scope") or ""), toks(a.title)) >= TITLE_SIM: return "similar title"
    cf = set(c.get("files") or [])
    if files and cf and jacc(files, cf) >= FILE_SIM: return "overlapping files"
    return None

def pr_matches(p, a, files):
    if a.branch and p.get("headRefName") == a.branch: return None  # our own PR: handled separately
    if a.work_id and norm_id(a.work_id) in norm_id(p.get("headRefName", "") + " " + p.get("title", "")) and len(norm_id(a.work_id)) >= 4:
        return "work id in open PR"
    if jacc(toks(p.get("title")), toks(a.title)) >= TITLE_SIM: return "similar title"
    pf = {x.get("path") for x in (p.get("files") or []) if isinstance(x, dict)}
    if files and pf and jacc(files, pf) >= FILE_SIM: return "overlapping files"
    return None

class Lock:
    def __enter__(self):
        if not Path(CLAIMS).is_dir():
            raise GateError("claim directory unavailable; explicit initialization required")
        self.f = open(os.path.join(CLAIMS, ".claim-gate.lock"), "w")
        t0 = time.time()
        while True:
            try: fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB); return self
            except BlockingIOError:
                if time.time() - t0 > 120: raise RuntimeError("claim lock timeout")
                time.sleep(0.5)
    def __exit__(self, *e): fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()

def canonical(resource):
    if not isinstance(resource, str) or not re.fullmatch(r"(?:repo|pr|browser|outbound|work):[a-zA-Z0-9_./:@-]+", resource):
        raise GateError("invalid resource key")
    if any(part in ("", ".", "..") for part in resource.split(":", 1)[1].split("/")):
        raise GateError("noncanonical resource key")
    return resource.lower()


def overlaps(a, b):
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def resources_for(row):
    if "resources" in row:
        return row["resources"]
    # Legacy claims remain conservative blockers until explicitly migrated.
    repo = row.get("repo", "").lower()
    if not repo:
        raise GateError("legacy claim lacks repo; explicit migration required")
    files = row.get("files", [])
    return [canonical("repo:" + repo + "/" + f) for f in files] if files else [canonical("repo:" + repo)]


def append_record(row, records):
    row = {k: v for k, v in row.items() if not k.startswith("_")}
    row["sequence"] = max((j.get("sequence", 0) for j in records), default=0) + 1
    row["created"] = now().isoformat()
    path = Path(CLAIMS) / ("gate-v2-%020d-%s.json" % (row["sequence"], secrets.token_hex(8)))
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(row, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    fd = os.open(CLAIMS, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return row


class Gate:
    """Local OS-trusted principal, bound by the launcher, never by model arguments.

    Uses the existing claim directory and lock, with append-only compatibility
    records. All four bots must migrate to this API before enforcement is global.
    """
    def __init__(self, owner):
        if owner not in {"bob", "grok", "webbob", "andrea", "karen", "codex"}:
            raise GateError("unknown launcher identity")
        self.owner = owner

    def claim(self, repo, work_id, resources, ttl=240, branch="", title="", check=None):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo) or not norm_id(work_id):
            raise GateError("invalid work identity")
        repo, work_id = repo.lower(), norm_id(work_id)
        resources = sorted(set(canonical(r) for r in resources))
        if not resources or len(resources) > 100:
            raise GateError("one to 100 resources required")
        expires = self._expires(ttl)
        with Lock():
            records = read_records()
            for c in live_claims(records):
                if ((c.get("repo", "").lower() == repo and norm_id(c.get("work_id", "")) == work_id)
                        or any(overlaps(a, b) for a in resources for b in resources_for(c))):
                    raise GateError("resource already owned; use token-bound renew")
            if check:
                check()
            token = secrets.token_urlsafe(32)
            row = dict(repo=repo, work_id=work_id, task=work_id, owner=self.owner,
                       resources=resources, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                       fence=max((j.get("sequence", 0) for j in records), default=0) + 1,
                       status="RUNNING", expires=expires, branch=branch, title=title, files=[])
            row = append_record(row, records)
            return self._public(row) | {"token": token}

    @staticmethod
    def _expires(ttl):
        if type(ttl) is not int or not 1 <= ttl <= 14400:
            raise GateError("ttl must be 1..14400 seconds")
        return (now() + dt.timedelta(seconds=ttl)).isoformat()

    @staticmethod
    def _public(row):
        return {k: v for k, v in row.items() if k != "token_hash" and not k.startswith("_")}

    def _owned(self, records, repo, work_id, token, fence):
        key = (repo.lower(), norm_id(work_id))
        item = latest_by_key(records).get(key)
        if not item:
            raise GateError("no current claim")
        row = item[1]
        digest = hashlib.sha256(token.encode()).hexdigest()
        if (row["owner"] != self.owner or not secrets.compare_digest(row.get("token_hash", ""), digest)
                or type(fence) is not int or row.get("fence") != fence
                or row["status"].upper() in DONE or dt.datetime.fromisoformat(row["expires"]) <= now()):
            raise GateError("expired, stale, or wrong-owner claim")
        # A legacy writer may have bypassed the new API. Deny conflicting history.
        for other in live_claims(records):
            if other["_file"] == row["_file"]:
                continue
            if any(overlaps(a, b) for a in row["resources"] for b in resources_for(other)):
                raise GateError("conflicting legacy claim")
        return row

    def renew(self, repo, work_id, token, fence, ttl=240):
        expires = self._expires(ttl)
        with Lock():
            records = read_records()
            row = self._owned(records, repo, work_id, token, fence)
            return self._public(append_record(dict(row, expires=expires), records))

    def release(self, repo, work_id, token, fence):
        with Lock():
            records = read_records()
            row = self._owned(records, repo, work_id, token, fence)
            return self._public(append_record(dict(row, status="RELEASED"), records))

    def get_owner(self, resource):
        resource = canonical(resource)
        with Lock():
            matches = [j for j in live_claims() if any(overlaps(resource, r) for r in resources_for(j))]
            if len(matches) > 1:
                raise GateError("conflicting ownership")
            return self._public(matches[0]) if matches else None

    @contextlib.contextmanager
    def execution(self, repo, work_id, token, fence, resource):
        """Hold the claim lock across admission AND the protected effect.

        Trusted executors use this context, not check-then-act over MCP. This
        serializes protected effects; callbacks must have bounded timeouts.
        """
        resource = canonical(resource)
        with Lock():
            row = self._owned(read_records(), repo, work_id, token, fence)
            if not any(resource == r or resource.startswith(r + "/") for r in row["resources"]):
                raise GateError("resource outside claim")
            yield self._public(row)


def main():
    ap = argparse.ArgumentParser(description="Token-bound successor to the local claim gate")
    ap.add_argument("cmd", choices=["claim", "pre-pr", "renew", "release", "get-owner"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work-id", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--branch", default="")
    ap.add_argument("--files", default="")
    ap.add_argument("--resource", action="append", default=[])
    ap.add_argument("--token", default="")
    ap.add_argument("--fence", type=int, default=0)
    ap.add_argument("--ttl-min", type=int, default=240)
    ap.add_argument("--pr", default="")
    a = ap.parse_args()
    gate = Gate(a.owner)
    files = set(filter(None, a.files.split(",")))
    resources = a.resource or ["repo:" + a.repo + "/" + f for f in files] or ["work:" + a.repo + "/" + a.work_id]
    def check_prs():
        for p in gh_open_prs(a.repo):
            if a.branch and p.get("headRefName") == a.branch:
                raise GateError("UPDATE_EXISTING PR #%s" % p["number"])
            why = pr_matches(p, a, files)
            if why:
                raise GateError("open PR collision: " + why)
    if a.cmd == "claim":
        result = gate.claim(a.repo, a.work_id, resources, a.ttl_min * 60, a.branch, a.title, check_prs)
    elif a.cmd in {"renew", "release"}:
        args = (a.repo, a.work_id, a.token, a.fence)
        result = gate.renew(*args, ttl=a.ttl_min * 60) if a.cmd == "renew" else gate.release(*args)
    elif a.cmd == "get-owner":
        result = gate.get_owner(resources[0])
    else:
        with gate.execution(a.repo, a.work_id, a.token, a.fence, resources[0]):
            check_prs()
            result = {"result": "OK_TO_CREATE"}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"result": "BLOCKED", "reason": type(exc).__name__ + ": " + str(exc)}))
        sys.exit(3)
