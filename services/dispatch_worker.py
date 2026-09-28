"""Execute a fenced chat task; persist the answer before releasing the lane."""
from __future__ import annotations

import hashlib
import contextlib
import json
import os
import re
import signal
import sys
import threading
from pathlib import Path

from state import CONDUCTOR, ROOT, atomic_write, lock, read_json
from lanes import ask, slot
import mini_worker
import result_acceptance
import pr_evidence
import draft_publish
import api_worker
from result_acceptance import ResultRejected, blocked_answer
from workspaces import prepare, git, analysis_workspace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue
from api_tasks import MODELS as WORKER_MODELS, REPORT_KINDS


def task_repository(prompt):
    for project, spec in project_catalog().items():
        if re.search(r"\b" + re.escape(project) + r"\b", prompt, re.I):
            return project, Path(spec["repo"]).expanduser().resolve()
    return "WebBob", Path(__file__).resolve().parents[1]


def project_catalog():
    # Ship new project mappings with the pinned release; retain local overrides.
    return {**read_json(Path(__file__).with_name("projects.json"), {}),
            **read_json(CONDUCTOR / "services/projects.json", {})}


def report_repository(row):
    source_id = row.get("source_job_id")
    if source_id:
        from state import jobs
        source = task_queue.tasks(ROOT).get(source_id) or jobs().get(source_id)
        if not source:
            raise RuntimeError("The assigned source job is no longer available")
        project, repo = task_repository(source.get("prompt", "") or source.get("project", ""))
        # Paths come only from server-owned jobs, never from model output.
        worktree = Path(source["worktree"]) if source.get("worktree") else None
        return source.get("project") or project, worktree if worktree and worktree.is_dir() else Path(source.get("repo") or repo)
    return task_repository(row["prompt"])


def prepare_task(record, coding):
    if not coding:
        return prepare(record)
    # Independent Git metadata is needed for conductor code tasks: the model's
    # sandbox denies writes to the live conductor, including its .git directory.
    # Shared objects are read-only; new commits/refs live in this private clone.
    folder = Path(record["worktree"])
    with lock("dispatch-workspace"):
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            git(ROOT, "clone", "--shared", "--no-checkout", record["repo"], str(folder))
            git(folder, "checkout", "-b", record["branch"], "HEAD")
            git(folder, "remote", "remove", "origin")
        if git(folder, "branch", "--show-current") != record["branch"]:
            raise RuntimeError("Private task branch ownership mismatch")
        hooks = folder / ".git/hooks"
        atomic_write(hooks / "pre-push", "#!/bin/sh\necho 'Web Bob tasks are local only' >&2\nexit 1\n")
        (hooks / "pre-push").chmod(0o700)
    return folder


def redact(text):
    # Do not persist provider output containing any loaded credential.
    for name, value in os.environ.items():
        if (name.endswith(("KEY", "TOKEN", "SECRET", "PASSWORD"))) and len(value) >= 8:
            text = text.replace(value, "[secret removed]")
    return re.sub(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{25,}|gh[pousr]_[A-Za-z0-9_]{25,})\b",
                  "[secret removed]", text)


def execute(identifier, token):
    row = task_queue.tasks(ROOT).get(identifier)
    if not row or row.get("claim_token") != token or row["status"] not in task_queue.ACTIVE:
        return 0
    stopped = threading.Event()
    heartbeat = None
    owns_task = False
    answer = ""
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(lock("dispatch-" + identifier, blocking=False))
            owns_task = True
            stack.enter_context(slot(row["worker"]))
            api_only = row["worker"] in task_queue.API_WORKERS
            kind = task_queue.task_kind(row["kind"], row["prompt"])
            if api_only and (kind not in ("analysis", *REPORT_KINDS) or row.get("publish_project")):
                raise ResultRejected(row["worker"] + " is API-only; this task needs files or command execution. "
                                     "Choose codex or cursor-agent, or supply the evidence in the request.")
            project, repo = (report_repository(row) if api_only and kind in REPORT_KINDS else
                             task_repository(row["prompt"]) if not api_only else (None, None))
            if project and project.lower() == "webjam" and row["kind"] == "coding":
                stack.enter_context(lock("webjam-coder", blocking=False))
                from jobs import external_webjam_lease
                from runtime import screen_sessions
                if external_webjam_lease(screen_sessions()):
                    raise BlockingIOError("External WebJam coder is active")
            if not task_queue.transition(ROOT, identifier, token, "running"):
                return 0

            def renew():
                while not stopped.wait(10):
                    try:
                        current = task_queue.transition(ROOT, identifier, token, "heartbeat")
                    except Exception:
                        current = None
                    if not current:
                        # command.run handles TERM by killing the entire model
                        # subprocess group. An expired worker cannot keep editing.
                        if not stopped.is_set():
                            os.kill(os.getpid(), signal.SIGTERM)
                        return

            heartbeat = threading.Thread(target=renew, daemon=True)
            heartbeat.start()
            review = (pr_evidence.load(row["prompt"], project_catalog())
                      if row["kind"] in ("analysis", "review") else None)
            folder = CONDUCTOR / "state/task-runs" / identifier
            folder.mkdir(parents=True, exist_ok=True)
            branch, cwd, base_sha = None, None, None
            coding = row["kind"] in ("coding", "artifact")
            evidence_metadata = None
            prompt = ("Web Bob assigned this task from Jeff. Complete it and return the actual result in your final answer. "
                      "Do not merely propose a plan or claim another worker will do it. If blocked, begin BLOCKER:. "
                      "Use the supplied evidence; do not invent observations.\n\n")
            if api_only:
                prompt += api_worker.RULES
            if review:
                if not api_only:
                    cwd = analysis_workspace(row["worker"])
                atomic_write(folder / "PR-EVIDENCE.json", json.dumps(review["metadata"], indent=2) + "\n")
                prompt += review["text"] + "\n\n"
            elif api_only and kind in REPORT_KINDS:
                body, evidence_metadata = api_worker.evidence(repo, row["worker"], row["prompt"], redact)
                atomic_write(folder / "REPO-EVIDENCE.json", json.dumps(evidence_metadata, indent=2) + "\n")
                prompt += body + "\n\n"
            elif not api_only and row["worker"] != "mini":
                branch = "draft/" + identifier
                record = dict(repo=str(repo), worktree=str(ROOT / "workspaces" / identifier),
                              branch=branch, job_dir=str(folder))
                cwd = prepare_task(record, coding)
                if row["kind"] == "coding":
                    base_sha = git(cwd, "rev-parse", "HEAD")
                prompt += ("Keep all work local: never push or create/modify a PR. "
                           "Use only the assigned worktree " + str(cwd) + " on " + branch + ". "
                           "For code changes, commit locally and report the SHA, changed paths and tests.\n\n")
                if row["kind"] == "coding":
                    prompt += result_acceptance.CODING_REQUIREMENTS + "\n"
                    checks = mini_worker.coding_commands(project)
                    if checks:
                        prompt += ("Before accepting or publishing your commit, the server will independently re-run: "
                                   + json.dumps(checks) + ". Leave the checkout ready to run these commands.\n")
            prompt += "TASK:\n" + row["prompt"]
            prompt += "\n" + result_acceptance.deliverable_requirements(row["prompt"], row["kind"])
            if row.get("publish_project"):
                prompt += ("\nThe server has Jeff's explicit authorization to push this project's assigned draft branch. "
                           "Your part is one useful, bounded improvement: inspect, fix, test and commit locally. "
                           "The server will perform and verify the draft push after accepting your local result. "
                           "Do not push yourself or mark the task blocked because you did not push. Return changes, tests and SHA in under 150 words.")
            if review:
                prompt += ("\nReturn a concise code review, at most 250 words. Lead with concrete bugs/risks and changed paths/lines, "
                           "or explicitly state no concrete defects found. Do not recap every changed file. End with testing limits.")
            if row["kind"] == "artifact":
                contents, destination = task_queue.file_request(row["prompt"])
                target = Path(destination)
                if target.is_symlink():
                    raise RuntimeError("Refusing a symlink destination")
                previous_mtime = target.stat().st_mtime_ns if target.exists() else None
                prompt += ("\nThis small file task explicitly authorizes writing only " + destination +
                           " outside the worktree. Write the requested text even if the file already exists, verify it, and return its path. "
                           "No repository changes or commit are needed. Keep the answer under 80 words.")
            atomic_write(folder / "prompt.txt", redact(prompt))
            if not task_queue.transition(ROOT, identifier, token, "executing", worktree=str(cwd) if cwd else None,
                                         branch=branch, project=project, repo=str(repo) if repo else None,
                                         model=WORKER_MODELS.get(row["worker"]),
                                         prompt_file=str(folder / "prompt.txt")):
                return 0
            answer = redact(mini_worker.execute(row) if row["worker"] == "mini" else ask(row["worker"], prompt, cwd=cwd, coding=coding,
                                timeout=90 if row["kind"] == "artifact" else 1800 if coding else 240,
                                purpose=("api-worker-research" if kind == "research" else "api-worker") if api_only else "pr-review" if review else "small-file" if row["kind"] == "artifact" else "small-review" if row["worker"] == "claude" else "webbob-" + identifier,
                                locked=True)).strip()
            result_acceptance.check_answer(row["prompt"], answer, kind=row["kind"])
            if review:
                metadata = review["metadata"]
                if not any(file["path"] in answer for file in metadata["files"]):
                    raise ResultRejected("PR review did not cite any changed file")
                answer = ("[PR #" + str(metadata["number"]) + "](" + metadata["url"] +
                          ") @ `" + metadata["headRefOid"][:7] + "` — static diff review by " + row["worker"] + ".\n\n" + answer)
            if row["kind"] == "artifact":
                if target.is_symlink() or not target.is_file() or target.read_text().rstrip("\n") != contents:
                    raise ResultRejected("Worker did not write the requested file contents")
                if target.stat().st_mtime_ns == previous_mtime:
                    raise ResultRejected("Worker left the preexisting file unchanged; no write verified")
                answer += "\n\nServer verified file: " + destination + "; SHA-256: " + hashlib.sha256(target.read_bytes()).hexdigest()
            if coding:
                if git(cwd, "branch", "--show-current") != branch:
                    raise ResultRejected("Worker changed its assigned draft branch")
                if git(cwd, "status", "--porcelain", "--untracked-files=normal"):
                    raise ResultRejected("Worker left uncommitted changes; task is not complete")
            coding_evidence = None
            if row["kind"] == "coding":
                result_acceptance.check_coding_answer(answer)
                head = git(cwd, "rev-parse", "HEAD")
                changed = git(cwd, "diff", "--name-only", base_sha, head).splitlines()
                diff = git(cwd, "diff", "--no-ext-diff", base_sha, head)
                if len(diff) > 60000:
                    raise ResultRejected("Coding diff exceeds bounded acceptance review; choose a smaller fix")
                validation = mini_worker.verify_coding(cwd, project, folder, redact)
                coding_evidence = dict(base_sha=base_sha, sha=head, changed_paths=changed, diff=diff,
                                       validation=validation)
                # Read test definitions from the assigned commit, with the existing safe evidence reader.
                definitions = {}
                for path in git(cwd, "ls-files").splitlines():
                    if (Path(path).name in ("AGENTS.md", "package.json", "pyproject.toml", "Makefile")
                            and api_worker.safe_source(cwd, path)):
                        definitions[path] = api_worker.read_source(cwd, path, 12000).decode("utf-8", "replace")
                coding_evidence["test_definitions"] = definitions
                coding_evidence = json.loads(redact(json.dumps(coding_evidence)))
                atomic_write(folder / "CODING-EVIDENCE.json", json.dumps(coding_evidence, indent=2) + "\n")
            if row["worker"] == "mini" or row["kind"] == "artifact":
                acceptance = dict(accepted=True, method="verified-execution")
            else:
                acceptance_task = row["prompt"]
                if row.get("publish_project"):
                    acceptance_task += ("\nDelegated worker scope: inspect, fix, test and commit locally. "
                                        "Evaluate that local work. The server, not this worker, performs and verifies the authorized draft push after acceptance.")
                acceptance = result_acceptance.accept(
                    acceptance_task, answer,
                    lambda instructions: ask(row["worker"], instructions, cwd=cwd, coding=False,
                                             timeout=120, purpose="result-acceptance", locked=True),
                    coding_evidence=coding_evidence, kind=row["kind"])
                acceptance = json.loads(redact(json.dumps(acceptance)))
                if coding_evidence is not None:
                    if (git(cwd, "rev-parse", "HEAD") != coding_evidence["sha"]
                            or git(cwd, "branch", "--show-current") != branch
                            or git(cwd, "status", "--porcelain")):
                        raise ResultRejected("Coding checkout changed after verification")
                    acceptance["coding_evidence"] = dict(
                        sha=coding_evidence["sha"], base_sha=base_sha, changed_paths=changed,
                        validation=validation, path=str(folder / "CODING-EVIDENCE.json"))
            publication = None
            if row.get("publish_project"):
                if not task_queue.transition(ROOT, identifier, token, "heartbeat"):
                    return 0
                publication = draft_publish.publish(row, cwd, folder, project_catalog())
                answer = ("Pushed [" + publication["project"] + " draft](" + publication["url"] + ") @ `" +
                          publication["sha"][:7] + "`; remote SHA verified.\n\n" + answer)
                if publication.get("pr_url"):
                    answer = "Draft PR: " + publication["pr_url"] + "\n" + answer
            # The queue is the result outbox. A result file alone is never proof
            # of completion, and a superseded claim cannot publish a result.
            digest = hashlib.sha256(answer.encode()).hexdigest()
            acceptance["result_sha256"] = digest
            report_path = None
            if api_only:
                if not task_queue.transition(ROOT, identifier, token, "heartbeat"):
                    return 0
                report_path = api_worker.save_report(CONDUCTOR, identifier, token, row["worker"], answer, redact)
            result = task_queue.transition(ROOT, identifier, token, "succeeded", result=answer,
                                           result_sha256=digest, worktree=str(cwd) if cwd else None,
                                           branch=branch, acceptance=acceptance,
                                           review_source=review["metadata"] if review else None, publication=publication,
                                           evidence=evidence_metadata,
                                           result_path=str(report_path) if report_path else None)
            stopped.set()
            if result:
                atomic_write(folder / "RESULT.md", answer + "\n")
            return 0 if result else 1
    except BlockingIOError:
        if owns_task:
            task_queue.transition(ROOT, identifier, token, "busy", error="Waiting for the shared worker lane")
        return 0
    except ResultRejected as exc:
        message = redact(str(exc))[:1500]
        task_queue.transition(ROOT, identifier, token, "rejected", error=message, rejected_result=answer,
                              acceptance=dict(accepted=False, reason=message))
        return 1
    except Exception as exc:
        message = redact(str(exc)) if isinstance(exc, RuntimeError) else type(exc).__name__
        task_queue.transition(ROOT, identifier, token, "retry", error=message[:1500])
        return 1
    finally:
        stopped.set()
        if heartbeat:
            heartbeat.join(timeout=1)


if __name__ == "__main__":
    raise SystemExit(execute(*sys.argv[1:3]))
