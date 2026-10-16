"""Exact-SHA review receipts and draft-only publication via official GitHub MCP.

Verifier, lease and inbox callbacks are trusted host adapters. Model-supplied
strings/QA files never become Karen or Jeff authority.
"""
import asyncio
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid


class GateDenied(ValueError):
    pass


def identity(repo, pr, sha):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise GateDenied("invalid repository")
    if type(pr) is not int or pr < 1 or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise GateDenied("PR and full commit SHA required")
    return repo.lower(), pr, sha


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReviewGate:
    def __init__(self, path, *, verify_karen, verify_jeff, post_review):
        if not all(callable(f) for f in (verify_karen, verify_jeff, post_review)):
            raise GateDenied("authenticated review, approval and inbox adapters required")
        self.path = Path(path)
        self.verify_karen, self.verify_jeff, self.post_review = verify_karen, verify_jeff, post_review
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise GateDenied("review store unavailable")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, repo TEXT, pr INTEGER, sha TEXT, payload TEXT, delivered INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS verdicts(seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, payload TEXT)")
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def request_review(self, repo, pr, sha, scope, evidence):
        repo, pr, sha = identity(repo, pr, sha)
        if not scope or not evidence or any(not isinstance(item, str) or len(item) > 300 for item in [scope, *evidence]):
            raise GateDenied("scope and evidence references required")
        payload = {"repo": repo, "pr": pr, "sha": sha, "scope": scope, "evidence": sorted(set(evidence)), "recipient": "karen"}
        request_id = digest(payload)
        payload["request_id"] = request_id
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO requests VALUES (?,?,?,?,?,0)", (request_id, repo, pr, sha, json.dumps(payload)))
        self.deliver_request(request_id)
        return payload

    def deliver_request(self, request_id):
        # Stable message ID makes an interrupted delivery safe to replay via the
        # shared inbox's idempotent post operation. No direct chat/email sending.
        with self.db() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                raise GateDenied("unknown review request")
            if row["delivered"]:
                return
            payload = json.loads(row["payload"])
        self.post_review(request_id, payload)
        with self.db() as db:
            db.execute("UPDATE requests SET delivered=1 WHERE id=?", (request_id,))

    def record_verdict(self, payload, authenticated_receipt):
        required = {"request_id", "repo", "pr", "sha", "scope", "evidence", "verdict", "reviewer", "expires"}
        if set(payload) != required or payload["reviewer"] != "karen" or payload["verdict"] not in {"PASS", "FAIL"}:
            raise GateDenied("independent Karen verdict required")
        identity(payload["repo"], payload["pr"], payload["sha"])
        if type(payload["expires"]) not in (int, float) or not time.time() < payload["expires"] <= time.time() + 86400:
            raise GateDenied("fresh bounded verdict expiry required")
        if self.verify_karen(digest(payload), authenticated_receipt) is not True:
            raise GateDenied("unverified Karen receipt")
        with self.db() as db:
            row = db.execute("SELECT payload FROM requests WHERE id=?", (payload["request_id"],)).fetchone()
            if not row:
                raise GateDenied("verdict has no matching review request")
            request = json.loads(row["payload"])
            if any(payload[k] != request[k] for k in ("repo", "pr", "sha", "scope", "evidence")):
                raise GateDenied("verdict does not match exact review scope")
            db.execute("INSERT INTO verdicts(request_id,payload) VALUES (?,?)", (payload["request_id"], json.dumps(payload)))

    def merge_readiness(self, repo, pr, current_sha, request_id, standing_approval):
        """Assessment only. Web Bob never receives a merge or undraft capability."""
        repo, pr, current_sha = identity(repo, pr, current_sha)
        with self.db() as db:
            row = db.execute("SELECT payload FROM verdicts WHERE request_id=? ORDER BY seq DESC LIMIT 1", (request_id,)).fetchone()
        if not row:
            return {"eligible_for_jeff_merge": False, "reason": "Karen verdict missing", "webbob_draft_only": True}
        verdict = json.loads(row["payload"])
        if (verdict["repo"], verdict["pr"], verdict["sha"]) != (repo, pr, current_sha):
            reason = "Karen verdict stale for current commit"
        elif verdict["verdict"] != "PASS" or verdict["expires"] <= time.time():
            reason = "Karen PASS missing or expired"
        elif self.verify_jeff({"repo": repo, "action": "merge", "pr": pr, "sha": current_sha}, standing_approval) is not True:
            reason = "Jeff standing approval missing or out of scope"
        else:
            reason = "Karen PASS and Jeff standing approval verified; Jeff owns merge"
        return {"eligible_for_jeff_merge": reason.startswith("Karen PASS and Jeff"),
                "reason": reason, "sha": current_sha, "webbob_draft_only": True}


class DraftPublisher:
    def __init__(self, session, *, ownership, verify_publish, read_branch_sha, read_pr):
        if not all(callable(f) for f in (ownership, verify_publish, read_branch_sha, read_pr)):
            raise GateDenied("publication authorization and fresh remote reads required")
        self.session, self.ownership, self.verify = session, ownership, verify_publish
        self.read_branch_sha, self.read_pr = read_branch_sha, read_pr

    async def publish(self, repo, branch, sha, title, body, approval):
        owner, name = repo.split("/", 1)
        identity(repo, 1, sha)
        if not re.fullmatch(r"draft/[A-Za-z0-9_.-]+", branch):
            raise GateDenied("draft branch required")
        payload = {"repo": repo, "branch": branch, "sha": sha, "title": title, "body": body, "draft": True}
        with self.ownership("repo:" + repo + "/refs/heads/" + branch):
            if await self.read_branch_sha(repo, branch) != sha:
                raise GateDenied("remote branch changed")
            if self.verify(digest(payload), approval) is not True:
                raise GateDenied("current exact publication approval required")
            # No update/merge/undraft method exists. Do not retry this call after
            # a lost response; existing draft publisher reconciliation must run.
            try:
                result = await asyncio.wait_for(self.session.call_tool("create_pull_request", {
                    "owner": owner, "repo": name, "head": branch, "base": "main",
                    "title": title, "body": body, "draft": True, "maintainer_can_modify": False}), 30)
                if result.isError:
                    return {"state": "uncertain", "sha": sha}
                pr = await self.read_pr(repo, branch)
            except Exception:
                return {"state": "uncertain", "sha": sha}
            if pr.get("head_sha") != sha or pr.get("draft") is not True or pr.get("state") != "open":
                return {"state": "uncertain", "sha": sha}
            return {"state": "draft", "sha": sha, "number": pr["number"], "url": pr["url"]}
