"""Serial, local integration of finished workers behind three mandatory gates.

Rebase a disposable worktree, never the author's branch. Only a green, reviewed
candidate can advance an unchecked-out integration ref via compare-and-swap.
The CLI is one tick; scheduling and model execution remain explicit opt-ins.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

try:
    from .command import run
    from .leases import LeaseStore, normalize
    from .planner import branch_ref, git, vendor
    from .project_board import ProjectBoard
    from .swarm_store import identifier, locked, write_json
except ImportError:
    from command import run
    from leases import LeaseStore, normalize
    from planner import branch_ref, git, vendor
    from project_board import ProjectBoard
    from swarm_store import identifier, locked, write_json


def commands(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("both test and eval suites must contain commands")
    for argv in value:
        if (not isinstance(argv, (list, tuple)) or not argv
                or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in argv)):
            raise ValueError("suite commands must be nonempty argument arrays, never shell strings")
    return value


def review_ok(receipt, candidate, authors):
    if not isinstance(receipt, dict) or receipt.get("approved") is not True or receipt.get("sha") != candidate:
        return False
    try:
        reviewer = receipt["llm"]
        review_vendor = vendor(reviewer, receipt.get("vendor"))
        return all(reviewer != author["llm"] and review_vendor != vendor(author["llm"], author.get("vendor"))
                   for author in authors)
    except (ValueError, KeyError, TypeError):
        return False


class MergeTrain:
    def __init__(self, conductor, project, *, tests, evals, reviewer=None, timeout=300):
        self.conductor, self.project = Path(conductor), identifier(project)
        self.board = ProjectBoard(conductor, project)
        self.tests, self.evals = commands(tests), commands(evals)
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
            raise ValueError("gate timeout must be between zero and one hour")
        self.timeout, self.reviewer = timeout, reviewer

    def _bounce(self, worker, stage, message, **fields):
        return self.board.update(worker, status="bounced", failure=dict(stage=stage, detail=message), **fields)

    def _gate(self, label, suite, cwd, environment):
        receipts = []
        for argv in suite:
            try:
                result = run(list(argv), cwd=str(cwd), env=environment, capture_output=True,
                             text=True, timeout=self.timeout)
                receipt = dict(stage=label, argv=list(argv), returncode=result.returncode,
                               output=((result.stdout or "") + (result.stderr or ""))[-12000:])
            except (OSError, subprocess.TimeoutExpired) as exc:
                receipt = dict(stage=label, argv=list(argv), returncode=None, output=type(exc).__name__)
            receipts.append(receipt)
            if receipt["returncode"] != 0:
                return False, receipts
        return True, receipts

    def _merged(self, row, candidate):
        # Persist the green result before release. A retry also releases an
        # orphaned lease if the process stopped between these two writes.
        result = self.board.update(row["worker"], status="merged", integrated_sha=candidate, failure=None)
        if row.get("lease"):
            LeaseStore(self.conductor, self.project).release(row["worker"], row["lease"]["token"])
            result = self.board.update(row["worker"], lease=None)
        if row.get("resolver_job"):
            def resolved(board):
                job_id, visited = row["resolver_job"], set()
                while job_id and job_id not in visited:
                    visited.add(job_id)
                    job = board["resolver_jobs"][job_id]
                    job.update(status="resolved", integrated_sha=candidate)
                    original = board["workers"][job["original_worker"]]
                    original.update(status="merged", integrated_sha=candidate, failure=None, updated_at=time.time())
                    job_id = original.get("resolver_job")
            self.board.change(resolved)
        return result

    def _conflict(self, row, repo, base, train_sha, worktree, authors):
        conflict_paths = git(worktree, "diff", "--name-only", "--diff-filter=U").splitlines()
        if not conflict_paths:
            return self._bounce(row["worker"], "rebase", "Rebase failed without content conflicts")
        job_id = "resolver-" + uuid.uuid4().hex[:16]
        job = dict(id=job_id, status="queued", role="conflict_resolution", llm="codex", vendor="openai",
                   branch="draft/swarm-" + job_id, original_worker=row["worker"], worker_sha=row["sha"],
                   integration_sha=train_sha, base_sha=base, intent=row["task"], conflicts=conflict_paths,
                   lease_paths=row["lease"]["paths"], review_authors=authors,
                   worker_diff=git(repo, "diff", "--binary", base, row["sha"], "--"),
                   integration_diff=git(repo, "diff", "--binary", base, train_sha, "--"), created_at=time.time())
        def enqueue(board):
            board["resolver_jobs"][job_id] = job
            board["workers"][row["worker"]].update(status="conflict", resolver_job_id=job_id,
                failure=dict(stage="rebase", detail="Queued Codex conflict resolution", conflicts=conflict_paths),
                updated_at=time.time())
        self.board.change(enqueue)
        return self.board.read()["workers"][row["worker"]]

    def process(self, worker):
        identifier(worker)
        with locked(self.conductor, "train-" + self.project):
            data = self.board.read()
            row = data["workers"][worker]
            repo = Path(data["repo"])
            ref = branch_ref(repo, data["integration_branch"])
            old = git(repo, "rev-parse", "--verify", ref)
            attempt = row.get("attempt") or {}
            if row["status"] == "merged":
                return self._merged(row, row["integrated_sha"])
            if row["status"] not in ("finished", "integrating"):
                raise ValueError("only finished workers enter the train")
            # Recovery after the atomic ref advance but before the board write.
            if attempt.get("green"):
                candidate = attempt["candidate_sha"]
                ancestor = run(["git", "-C", str(repo), "merge-base", "--is-ancestor", candidate, old],
                               capture_output=True, text=True, timeout=60)
                if ancestor.returncode == 0:
                    return self._merged(row, candidate)
            if row["role"] not in ("architecture", "hard_fix", "conflict_resolution", "refactor", "feature", "tests"):
                raise ValueError("only coding workers enter the train")
            worker_ref = branch_ref(repo, row["branch"])
            if worker_ref == ref:
                raise ValueError("worker and integration branches must differ")
            if "branch " + ref in git(repo, "worktree", "list", "--porcelain").splitlines():
                return self._bounce(worker, "integration", "Integration branch is checked out; use a dedicated unchecked-out ref")
            if git(repo, "rev-parse", "--verify", worker_ref) != row["sha"]:
                return self._bounce(worker, "worker", "Worker branch moved after finish; resubmit the current SHA")
            leases = LeaseStore(self.conductor, self.project, repo)
            if not row.get("lease") or row["lease"] not in leases.list():
                return self._bounce(worker, "lease", "Worker no longer owns its paths")
            base = git(repo, "merge-base", old, row["sha"])
            # Include both sides of renames; an owned destination is not enough.
            changed = git(repo, "diff", "--no-renames", "--name-only", "-z", base, row["sha"], "--")
            paths = normalize(changed.rstrip("\x00").split("\x00"), repo) if changed else []
            allowed = row["lease"]["paths"]
            if any(not any(a == "." or p == a or p.startswith(a + "/") for a in allowed) for p in paths):
                return self._bounce(worker, "lease", "Worker changed files outside its lease")
            authors = row.get("review_authors", []) + [dict(llm=row["llm"], vendor=row["vendor"])]
            self.board.update(worker, status="integrating", attempt=None, gates=[])
            parent = self.conductor / "state/swarm-runs"
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=self.project + "-", dir=parent) as folder:
                folder = Path(folder)
                worktree = folder / "candidate"
                git(repo, "worktree", "add", "--detach", str(worktree), row["sha"])
                advanced_sha = None
                try:
                    rebased = run(["git", "-C", str(worktree), "-c", "core.hooksPath=/dev/null",
                                   "-c", "rebase.autoStash=false", "-c", "rebase.updateRefs=false",
                                   "-c", "rerere.enabled=false", "rebase", "--onto", old, base],
                                  capture_output=True, text=True, timeout=60,
                                  env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_EDITOR="true"))
                    if rebased.returncode:
                        return self._conflict(row, repo, base, old, worktree, authors)
                    candidate = git(worktree, "rev-parse", "HEAD")
                    context = dict(project=self.project, worker=worker, sha=candidate, worker_sha=row["sha"],
                                   integration_sha=old, intent=row["task"], authors=authors,
                                   diff=git(worktree, "diff", "--binary", old, candidate, "--"),
                                   worktree=str(worktree))
                    # Gates receive a private state root and the rebased checkout.
                    gate_root = folder / "gate-root"
                    (gate_root / "conductor").mkdir(parents=True)
                    environment = dict(os.environ, BOB_ROOT=str(gate_root), GIT_TERMINAL_PROMPT="0")
                    receipts = []
                    for stage, suite in (("tests", self.tests), ("evals", self.evals)):
                        green, results = self._gate(stage, suite, worktree, environment)
                        receipts.extend(results)
                        if not green:
                            return self._bounce(worker, stage, results[-1]["output"], gates=receipts)
                    review = self.reviewer(context) if self.reviewer else None
                    if not review_ok(review, candidate, authors):
                        return self._bounce(worker, "review", "Missing, red, stale, or same-vendor review", gates=receipts)
                    # Gates/review must not commit or modify the checkout they certify.
                    if git(worktree, "rev-parse", "HEAD") != candidate or git(worktree, "status", "--porcelain", "--untracked-files=no"):
                        return self._bounce(worker, "checkout", "A gate changed the candidate", gates=receipts)
                    if git(repo, "rev-parse", worker_ref) != row["sha"]:
                        return self._bounce(worker, "worker", "Worker branch moved during gates", gates=receipts)
                    if row["lease"] not in leases.list():
                        return self._bounce(worker, "lease", "Lease changed during gates", gates=receipts)
                    if "branch " + ref in git(repo, "worktree", "list", "--porcelain").splitlines():
                        return self._bounce(worker, "integration", "Integration branch was checked out during gates", gates=receipts)
                    git(repo, "merge-base", "--is-ancestor", old, candidate)
                    self.board.update(worker, gates=receipts, review=review,
                        attempt=dict(base_sha=old, candidate_sha=candidate, green=True))
                    advanced = run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null",
                                    "update-ref", ref, candidate, old],
                                   capture_output=True, text=True, timeout=60)
                    if advanced.returncode:
                        return self._bounce(worker, "integration", "Integration tip moved; rerun gates on its new tip", gates=receipts)
                    advanced_sha = candidate
                    return self._merged(row, candidate)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    if advanced_sha:
                        # The ref is already green. Never record a false bounce;
                        # leave the saved attempt for the next tick to reconcile.
                        raise
                    return self._bounce(worker, "infrastructure", type(exc).__name__ + ": " + str(exc)[:1000])
                finally:
                    # Only this uniquely allocated, detached worktree is removed.
                    git(repo, "worktree", "remove", "--force", str(worktree))

    def tick(self):
        board = self.board.read()
        def pending(row):
            job = board["resolver_jobs"].get(row.get("resolver_job"), {})
            return (row["status"] in ("finished", "integrating") or
                    (row["status"] == "merged" and (row.get("lease") or (job and job["status"] != "resolved"))))
        return [self.process(worker) for worker, row in board["workers"].items() if pending(row)]


def command_reviewer(argv, timeout):
    """Trusted reviewer adapter: context JSON in argv, receipt JSON on stdout."""
    commands([argv])
    def review(context):
        path = Path(context["worktree"]).parent / "review-context.json"
        write_json(path, context)
        result = run([*argv, str(path)], cwd=context["worktree"], capture_output=True,
                     text=True, timeout=timeout, check=True)
        return json.loads(result.stdout)
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conductor", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--config", required=True, type=Path, help="Trusted JSON: tests, evals, review_command, timeout")
    parser.add_argument("--worker", help="Omit to process all finished workers once")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    reviewer = command_reviewer(config["review_command"], config.get("timeout", 300))
    train = MergeTrain(args.conductor, args.project, tests=config["tests"], evals=config["evals"],
                       reviewer=reviewer, timeout=config.get("timeout", 300))
    results = [train.process(args.worker)] if args.worker else train.tick()
    # Failures and reviews stay in the private board; avoid printing their output.
    print(json.dumps([dict(worker=r["worker"], status=r["status"], sha=r.get("integrated_sha")) for r in results]))
    return int(any(r["status"] != "merged" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
