"""Contract-first assignment and strength-based roles for the opt-in swarm.

This service records jobs; it does not launch models or deploy anything.
Cursor's underlying vendor must be declared, because Cursor is a tool, not a vendor.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    from .command import run
    from .leases import LeaseStore
    from .project_board import ProjectBoard
    from .swarm_store import identifier, locked
except ImportError:
    from command import run
    from leases import LeaseStore
    from project_board import ProjectBoard
    from swarm_store import identifier, locked


VENDORS = {"codex": "openai", "claude": "anthropic", "gemini": "google", "minimax": "minimax"}
ROLES = {
    "architecture": ("codex", "claude"), "hard_fix": ("codex",),
    "conflict_resolution": ("codex",), "deploy": ("codex",),
    "design": ("claude",), "reply_quality": ("claude",), "ux_quality": ("claude",),
    "refactor": ("claude",), "final_review": ("claude",),
    "feature": ("cursor",), "tests": ("cursor",),
    "audit": ("gemini",), "gap_analysis": ("gemini",), "planning": ("gemini",),
    "second_review": ("gemini",), "review": ("minimax", "gemini", "claude"),
    "test_cases": ("minimax",), "eval_grading": ("minimax",),
    "push_critique": ("minimax", "gemini"),
}
REVIEW_ROLES = {"review", "final_review", "second_review", "push_critique", "eval_grading"}
WRITE_ROLES = {"architecture", "hard_fix", "conflict_resolution", "refactor", "feature", "tests"}


def vendor(llm, declared=None):
    if llm not in (*VENDORS, "cursor"):
        raise ValueError("unknown or forbidden model; never Grok/xAI")
    if llm == "cursor":
        if declared not in set(VENDORS.values()):
            raise ValueError("Cursor requires its actual allowlisted underlying vendor")
        return declared
    if declared is not None and declared != VENDORS[llm]:
        raise ValueError("declared vendor does not match model")
    return VENDORS[llm]


def route(role, *, available=None, author=None, author_vendor=None, requested=None):
    if role not in ROLES:
        raise ValueError("unknown swarm role")
    choices = ROLES[role]
    if requested is not None and requested not in choices:
        raise ValueError("model is not allowed for this role")
    if role in REVIEW_ROLES:
        if author is None:
            raise ValueError("review routing requires the author")
        author_vendor = vendor(author, author_vendor)
    ready = set(available) if available is not None else set(choices)
    for llm in choices:
        if llm not in ready or (requested and llm != requested):
            continue
        if role in REVIEW_ROLES and (llm == author or vendor(llm) == author_vendor):
            continue
        return llm
    raise ValueError("no eligible model available for this role")


def git(repo, *args):
    output = run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                 capture_output=True, text=True, timeout=60, check=True).stdout
    # NUL-delimited filenames must retain leading/trailing whitespace verbatim.
    return output if "-z" in args else output.rstrip("\n")


def branch_ref(repo, branch):
    if not isinstance(branch, str) or not branch.startswith(("draft/", "integration/")):
        raise ValueError("swarm branches must use draft/ or integration/")
    ref = "refs/heads/" + branch
    git(repo, "check-ref-format", ref)
    return ref


class Planner:
    def __init__(self, conductor, project):
        self.conductor, self.project = Path(conductor), identifier(project)
        self.board = ProjectBoard(conductor, project)

    def initialize(self, repo, integration_branch, contract_sha):
        repo = Path(repo).resolve()
        ref = branch_ref(repo, integration_branch)
        contract = git(repo, "rev-parse", "--verify", contract_sha + "^{commit}")
        git(repo, "merge-base", "--is-ancestor", contract, ref)
        return self.board.initialize(repo, integration_branch, contract)

    def assign(self, worker, task, role, branch, paths, *, llm=None, model_vendor=None,
               available=None, author=None, author_vendor=None):
        identifier(worker)
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task intent is required")
        selected = route(role, available=available, requested=llm, author=author, author_vendor=author_vendor)
        source_vendor = vendor(selected, model_vendor)
        with locked(self.conductor, "plan-" + self.project):
            data = self.board.read()
            if worker in data["workers"]:
                raise ValueError("worker ID already assigned; use a new ID")
            ref = branch_ref(data["repo"], branch)
            if branch == data["integration_branch"]:
                raise ValueError("workers cannot own the integration branch")
            if any(r["branch"] == branch and r["status"] not in ("merged", "cancelled") for r in data["workers"].values()):
                raise ValueError("worker branch already assigned")
            sha = git(data["repo"], "rev-parse", "--verify", ref)
            git(data["repo"], "merge-base", "--is-ancestor", data["contract_sha"], sha)
            leases = LeaseStore(self.conductor, self.project, data["repo"])
            # Shared hot-file refactors precede parallel feature work.
            lease = leases.claim(worker, ["."] if role == "refactor" else paths) if role in WRITE_ROLES else None
            row = dict(worker=worker, llm=selected, vendor=source_vendor, lease=lease,
                       task=task, role=role, branch=branch, sha=sha, base_sha=sha,
                       status="assigned", updated_at=time.time())
            # If a write fails, retain ownership: an orphan lease is safer than
            # allowing a second task into paths that may already be in use.
            self.board.change(lambda board: board["workers"].__setitem__(worker, row))
            return row

    def start(self, worker, token):
        with locked(self.conductor, "plan-" + self.project):
            row = self._owned(worker, token)
            if row["status"] not in ("assigned", "bounced"):
                raise ValueError("worker is not ready to start")
            return self.board.update(worker, status="running", failure=None, attempt=None)

    def _owned(self, worker, token):
        data = self.board.read()
        row = data["workers"][worker]
        lease = row.get("lease")
        if lease:
            owned = LeaseStore(self.conductor, self.project, data["repo"]).list()
            if lease["token"] != token or lease not in owned:
                raise ValueError("worker no longer owns its lease")
        elif token is not None:
            raise ValueError("unexpected ownership token")
        return row

    def finish(self, worker, token, sha):
        with locked(self.conductor, "plan-" + self.project):
            data = self.board.read()
            row = self._owned(worker, token)
            if row["status"] not in ("assigned", "running", "bounced"):
                raise ValueError("worker cannot finish from this state")
            current = git(data["repo"], "rev-parse", "--verify", branch_ref(data["repo"], row["branch"]))
            if sha != current:
                raise ValueError("finished SHA must equal the full worker branch tip")
            git(data["repo"], "merge-base", "--is-ancestor", row["base_sha"], current)
            return self.board.update(worker, sha=current, status="finished", failure=None, attempt=None)

    def claim_resolver(self, job_id, worker):
        """Claim a durable Codex-only job and atomically transfer its path fence."""
        identifier(worker)
        with locked(self.conductor, "plan-" + self.project):
            data = self.board.read()
            job = data["resolver_jobs"][job_id]
            if job["status"] == "claimed" and job.get("worker") == worker:
                return data["workers"][worker]
            retry = job["status"] == "claiming" and job.get("worker") == worker
            if (job["status"] != "queued" and not retry) or worker in data["workers"]:
                raise ValueError("resolver job is not available")
            original = data["workers"][job["original_worker"]]
            llm = route("conflict_resolution")
            ref = branch_ref(data["repo"], job["branch"])
            existing = run(["git", "-C", data["repo"], "show-ref", "--verify", "--hash", ref],
                           capture_output=True, text=True, timeout=60)
            if existing.returncode == 0 and (not retry or existing.stdout.strip() != job["worker_sha"]):
                raise ValueError("resolver branch already exists or moved")
            self.board.change(lambda board: board["resolver_jobs"][job_id].update(status="claiming", worker=worker))
            # A new branch preserves the author's branch and avoids force pushes.
            if existing.returncode != 0:
                git(data["repo"], "branch", job["branch"], job["worker_sha"])
            lease = LeaseStore(self.conductor, self.project, data["repo"]).transfer(
                original["worker"], original["lease"]["token"], worker)
            row = dict(worker=worker, llm=llm, vendor=vendor(llm), lease=lease,
                       task=job["intent"], role="conflict_resolution", branch=job["branch"],
                       sha=job["worker_sha"], base_sha=job["base_sha"], status="assigned",
                       resolver_job=job_id, review_authors=job["review_authors"], updated_at=time.time())
            def apply(board):
                board["workers"][worker] = row
                board["workers"][original["worker"]].update(lease=None, resolved_by=worker)
                board["resolver_jobs"][job_id].update(status="claimed", worker=worker)
            self.board.change(apply)
            return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conductor", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("action", choices=("init", "assign", "start", "finish", "claim-resolver", "board"))
    parser.add_argument("--spec", type=Path, help="JSON object of method arguments")
    args = parser.parse_args()
    planner = Planner(args.conductor, args.project)
    values = json.loads(args.spec.read_text()) if args.spec else {}
    action = {"init": planner.initialize, "assign": planner.assign, "start": planner.start,
              "finish": planner.finish, "claim-resolver": planner.claim_resolver, "board": planner.board.read}[args.action]
    print(json.dumps(action(**values), indent=2))


if __name__ == "__main__":
    main()
