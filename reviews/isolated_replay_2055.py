#!/usr/bin/env python3
"""Ten historical cross-project turns using private queues and local publication.

The application, workers, acceptance checks and publication guards are real.
Only the publication transport is replaced: Git writes to local bare remotes,
and draft PR operations use an explicitly labelled local file-backed adapter.
This is private integration evidence, never a claim of 19 production turns.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from unittest.mock import patch

CODE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(CODE / name) for name in ("webchat", "services", "state", "reviews")]
from texting_deploy_record import atomic_json, require_disk_space

PROJECTS = ("WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football")
SCOPE = "isolated-local-remotes"
CURSOR_MODEL = "gpt-5.6-sol-high"  # Confirmed in cursor-agent --list-models on 2026-09-28.
SOURCE_FILES = ("reviews/isolated_replay_2055.py", "webchat/app.py", "webchat/integration_rubric.py",
                "webchat/reply_authority.py",
                "webchat/task_dispatch.py", "webchat/dispatch_receipts.py", "webchat/live_status_snapshot.py",
                "webchat/status_observation.py", "webchat/build_info.py", "services/dispatch_worker.py",
                "services/draft_publish.py", "services/command.py", "services/lanes.py", "services/api_worker.py",
                "services/result_acceptance.py", "services/mini_worker.py", "services/workspaces.py",
                "services/budget.py", "services/state.py", "state/task_queue.py", "state/ledger.py",
                "webchat/fixtures/integrate_sessions_0927.json")
CHAT_IMPORTS = dict(app="webchat/app.py", ledger="state/ledger.py", task_queue="state/task_queue.py",
                    live_status_snapshot="webchat/live_status_snapshot.py", providers="webchat/providers.py")
WORKER_IMPORTS = dict(state="services/state.py", budget="services/budget.py", lanes="services/lanes.py",
                      dispatch_worker="services/dispatch_worker.py", task_queue="state/task_queue.py",
                      result_acceptance="services/result_acceptance.py", draft_publish="services/draft_publish.py",
                      mini_worker="services/mini_worker.py", api_worker="services/api_worker.py",
                      workspaces="services/workspaces.py")


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    return subprocess.check_output(["git", "-C", str(repo), *map(str, args)],
                                   env=env, stderr=subprocess.PIPE, text=True, timeout=120).strip()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size)


def imported_modules(names, candidate=CODE):
    result = {}
    for name, relative in names.items():
        actual = Path(sys.modules[name].__file__).resolve()
        require(actual == candidate / relative, "Wrong candidate module imported: " + name + " " + str(actual))
        result[name] = dict(path=str(actual), sha256=digest(actual))
    return result


def explicit_cursor_model(argv):
    argv = list(argv)
    if Path(str(argv[0])).name in ("cursor-agent", "agent"):
        require("--model" not in argv, "Unexpected preexisting Cursor model override")
        argv[1:1] = ["--model", CURSOR_MODEL]
    return argv


def private_context_providers(root, private, runner=None):
    """Use private prompt snapshots while retaining the real provider/meter root."""
    from providers import Providers, Redactor, run
    class PrivateContextProviders(Providers):
        def context_root(self, conversation_id=None):
            return private
    return PrivateContextProviders(root, Redactor(root, ""), runner=runner or run)


def lane_availability(worker_name, *, now=None, probe_lease=True, check_reservations=True):
    """Read the shared eligibility gates before consuming a private claim attempt."""
    import budget
    import lanes
    from state import jobs, read_json
    from task_dispatch import task_queue
    now = time.time() if now is None else now
    cooldown = read_json(lanes.CONDUCTOR / "lane-cooldowns.json", {}).get(worker_name, {})
    retry_at = cooldown.get("retry_at", 0)
    if retry_at > now:
        return dict(ready=False, reason="shared cooldown", retry_at=retry_at)
    try:
        usage = budget.check(worker_name)
    except budget.BudgetExceeded:
        return dict(ready=False, reason="shared budget exhausted")
    if check_reservations:
        live = task_queue.tasks(lanes.CONDUCTOR.parent)
        if sum(row["worker"] == worker_name and row["status"] in task_queue.ACTIVE
               for row in live.values()) >= task_queue.capacity(worker_name):
            return dict(ready=False, reason="shared live claim reserved")
        if any(row.get("engine") == worker_name and row["state"] in ("launched", "running")
               and row.get("managed") for row in jobs().values()):
            return dict(ready=False, reason="shared scheduled job reserved")
    if probe_lease:
        try:
            with lanes.slot(worker_name):
                pass
        except BlockingIOError:
            return dict(ready=False, reason="shared lane lease busy")
        except budget.BudgetExceeded:
            return dict(ready=False, reason="shared budget exhausted")
    return dict(ready=True, reason="shared lane available", budget_tier=usage.get("tier"))


def claim_when_ready(private, worker_name, *, now=None):
    from task_dispatch import task_queue
    readiness = lane_availability(worker_name, now=now)
    return (task_queue.claim(private, worker_name) if readiness["ready"] else None), readiness


@contextlib.contextmanager
def ready_worker_slot(worker_name, original_slot):
    """A cooldown/budget race after claiming uses the existing busy/refund event."""
    with original_slot(worker_name):
        readiness = lane_availability(worker_name, probe_lease=False, check_reservations=False)
        if not readiness["ready"]:
            raise BlockingIOError(readiness["reason"])
        yield


def capture_cli_output(folder, *, result=None, error=None, redact=str):
    """Persist bounded, redacted transport evidence without changing CLI parsing."""
    receipt = dict(transport="actual-cli-output", exit=result.returncode if result is not None else None)
    for field in ("stdout", "stderr"):
        value = getattr(result if result is not None else error, field, "") or ""
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        raw = redact(value).encode()
        receipt[field] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                              tail=raw[-32768:].decode("utf-8", "replace"), truncated=len(raw) > 32768)
    if error is not None:
        receipt["error"] = redact(type(error).__name__ + ": " + str(error))[-2000:]
    path = Path(folder) / ("CLI-OUTPUT-" + uuid.uuid4().hex + ".json")
    atomic_json(path, receipt, exclusive=True)
    return artifact(path)


def verify_imports(receipt, names, candidate):
    require(set(receipt) == set(names), "Runtime module binding incomplete")
    for name, relative in names.items():
        require(receipt[name] == dict(path=str(candidate / relative), sha256=digest(candidate / relative)),
                "Runtime module binding changed: " + name)


def checked_artifact(receipt, private):
    path = Path(receipt["path"]).resolve(strict=True)
    require(path.is_relative_to(private) and path.is_file(), "Artifact escapes the private replay")
    require(path.stat().st_size == receipt["bytes"] and digest(path) == receipt["sha256"],
            "Private replay artifact changed: " + str(path))
    return path


def source_state(repo):
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    index = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    return dict(head=git(repo, "rev-parse", "HEAD"),
                refs=git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
                status=git(repo, "status", "--porcelain", "--untracked-files=normal"),
                index_sha256=digest(index) if index.is_file() else None, common=str(common))


def private_sessions(expected=None):
    from integration_rubric import sessions
    rows = copy.deepcopy(expected if expected is not None else sessions())
    # Selection is by original session identity, never a replacement prompt.
    rows = [row for row in rows if row["source_id"].startswith(("8126301c-", "65a5d782-"))]
    require(len(rows) == 2 and [len(row["exchanges"]) for row in rows] == [9, 1],
            "Expected the original 9+1 cross-project sessions")
    require(sum(x["expected"].startswith("projects") for s in rows for x in s["exchanges"]) == 2,
            "Private replay lost a project dispatch turn")
    return rows


def prepare(root, candidate, output):
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    require(candidate == CODE, "Run the harness from the candidate checkout")
    require(not git(candidate, "status", "--porcelain"), "Candidate must be committed and clean")
    sha = git(candidate, "rev-parse", "HEAD")
    require(not Path(output).exists(), "Never overwrite an existing private replay proof")
    private = root / "workspaces" / ("texting-private-2055-" + uuid.uuid4().hex[:12])
    free = [require_disk_space(root, candidate, "ISOLATED_PREPARE")]
    private.mkdir(mode=0o700)
    (private / "conductor/services").mkdir(parents=True)
    (private / "workspaces").mkdir()
    (private / "remotes").mkdir()
    (private / "sources").mkdir()
    catalog = json.loads((candidate / "services/projects.json").read_text())
    overrides = root / "conductor/services/projects.json"
    if overrides.exists():
        catalog.update(json.loads(overrides.read_text()))
    sources, projects = {}, {}
    for index, name in enumerate(PROJECTS):
        free.append(require_disk_space(root, candidate, "ISOLATED_CLONE_" + str(index)))
        spec = next(value for label, value in catalog.items() if label.lower() == name.lower())
        source = Path(spec["repo"]).expanduser().resolve(strict=True)
        require(not source.is_relative_to(private), "Original source must precede isolation")
        before = source_state(source)
        destination = private / "sources" / str(index)
        # Independent refs/index; alternates only read committed source objects.
        git(private, "clone", "--shared", "--no-checkout", str(source), str(destination))
        git(destination, "checkout", "--detach", before["head"])
        git(destination, "remote", "remove", "origin")
        remote = private / "remotes" / (str(index) + ".git")
        git(private, "init", "--bare", str(remote))
        require(source_state(source) == before, "Source repository changed during clone: " + name)
        sources[name] = dict(path=str(source), before=before, clone=str(destination),
                             sha=before["head"], remote=str(remote))
        projects[name] = dict(repo=str(destination), remote="isolated2055/project" + str(index))
    atomic_json(private / "conductor/services/projects.json", projects)
    manifest = dict(scope=SCOPE, sha=sha, candidate=str(candidate), real_root=str(root),
                    private_root=str(private), projects=projects, sources=sources,
                    source_files={name: digest(candidate / name) for name in SOURCE_FILES},
                    shared_meter=str(root / "conductor/ledger"),
                    shared_locks=str(root / "conductor/locks"), free_space=free)
    atomic_json(private / "manifest.json", manifest)
    return private / "manifest.json"


class LocalPublication:
    """A strict transport seam, not a replacement for publication quality checks."""
    def __init__(self, manifest):
        self.manifest = manifest
        self.private = Path(manifest["private_root"]).resolve()
        self.remotes = {spec["remote"]: Path(manifest["sources"][name]["remote"]).resolve()
                        for name, spec in manifest["projects"].items()}
        self.receipts = self.private / "local-draft-prs"
        self.receipts.mkdir(exist_ok=True)

    def local_remote(self, remote):
        require(remote in self.remotes, "Unapproved publication destination")
        path = self.remotes[remote]
        require(path.is_relative_to(self.private / "remotes") and path.is_dir(),
                "Publication remote escaped the private replay")
        return path

    def receipt_path(self, remote, branch):
        require(re.fullmatch(r"draft/webchat-[a-f0-9]{32}", branch), "Invalid private draft branch")
        self.local_remote(remote)
        return self.receipts / (remote.replace("/", "_") + "-" + branch.split("/")[1] + ".json")

    def run(self, argv, **kwargs):
        from command import run
        argv = list(map(str, argv))
        if argv and argv[0] == "gh":
            require(len(argv) > 2 and argv[1:3] in (["pr", "list"], ["pr", "create"]),
                    "Private adapter forbids this GitHub operation")
            remote = argv[argv.index("--repo") + 1]
            branch = argv[argv.index("--head") + 1]
            bare = self.local_remote(remote)
            path = self.receipt_path(remote, branch)
            sha = git(bare, "rev-parse", "refs/heads/" + branch)
            if argv[2] == "create":
                require("--draft" in argv and not path.exists(), "Local PR must be a new draft")
                body = Path(argv[argv.index("--body-file") + 1]).resolve()
                require(body.is_relative_to(self.private) and body.is_file(), "Draft body is outside isolation")
                atomic_json(path, dict(transport="local-draft-pr-adapter", isDraft=True, headRefOid=sha,
                                      branch=branch, remote=str(bare), body=artifact(body),
                                      url=path.as_uri()), exclusive=True)
            rows = [json.loads(path.read_text())] if path.exists() else []
            if rows:
                require(rows[0]["headRefOid"] == sha and rows[0]["isDraft"] is True,
                        "Local draft PR SHA or draft state changed")
            return subprocess.CompletedProcess(argv, 0, json.dumps(rows) if argv[2] == "list" else path.as_uri(), "")
        require(argv and argv[0] == "git", "Private publication permits only Git/PR transport")
        matches = [(index, arg) for index, arg in enumerate(argv) if arg.startswith("https://github.com/")]
        require(len(matches) == 1, "Publication command lacks one explicit approved URL")
        index, url = matches[0]
        require(url.endswith(".git"), "Unrecognized publication URL")
        remote = url[len("https://github.com/"):-4]
        bare = self.local_remote(remote)
        require("--force" not in argv and "-f" not in argv, "Forced publication forbidden")
        if "push" in argv:
            require("-C" in argv, "Private push needs a checkout")
            cwd = Path(argv[argv.index("-C") + 1]).resolve()
            require(cwd.is_relative_to(self.private / "workspaces"), "Private push checkout escaped")
            require(re.fullmatch(r"[a-f0-9]{40}:refs/heads/draft/webchat-[a-f0-9]{32}", argv[-1]),
                    "Private push must publish one exact task ref")
        else:
            require(argv[1:3] == ["ls-remote", "--exit-code"] and
                    re.fullmatch(r"refs/heads/draft/webchat-[a-f0-9]{32}", argv[-1]),
                    "Unrecognized private verification operation")
        argv[index] = str(bare)
        env = dict(kwargs.pop("env", os.environ), GIT_TERMINAL_PROMPT="0",
                   GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
        return run(argv, env=env, **kwargs)


def protected_paths(manifest):
    paths = [Path(manifest["candidate"]), Path(manifest["real_root"]) / "conductor",
             Path(manifest["private_root"]) / "sources", Path(manifest["private_root"]) / "remotes",
             Path(manifest["private_root"]) / "local-draft-prs"]
    for source in manifest["sources"].values():
        paths.extend((Path(source["path"]), Path(source["before"]["common"])))
    return sorted({str(path.resolve()) for path in paths})


def extra_policy(manifest):
    return " (deny file-write* " + " ".join("(subpath " + json.dumps(p) + ")" for p in protected_paths(manifest)) + ")"


def worker(manifest_path, identifier, token):
    manifest = json.loads(Path(manifest_path).read_text())
    root, private = Path(manifest["real_root"]), Path(manifest["private_root"])
    require(os.environ.get("BOB_ROOT") == str(root), "Worker must retain the real metered BOB_ROOT")
    import state
    import budget
    import lanes
    import dispatch_worker
    import draft_publish
    import mini_worker
    require(state.ROOT == root and budget.CONDUCTOR == root / "conductor" and
            lanes.CONDUCTOR == root / "conductor", "Budget and lane locks must remain shared")
    require(git(CODE, "rev-parse", "HEAD") == manifest["sha"], "Worker code SHA changed")
    require_disk_space(root, CODE, "ISOLATED_WORKER")
    worker_runtime = dict(imports=imported_modules(WORKER_IMPORTS), shared_root=str(state.ROOT),
                          shared_meter=str(budget.CONDUCTOR / "ledger"), shared_locks=str(lanes.CONDUCTOR / "locks"),
                          model_invocations=[], cli_outputs=[])
    folder = private / "conductor/state/task-runs" / identifier
    folder.mkdir(parents=True, exist_ok=True)
    atomic_json(folder / "RUNTIME.json", worker_runtime)
    transport = LocalPublication(manifest)
    original_sandbox = lanes.sandbox_command
    original_checks = mini_worker.run
    original_publish = draft_publish.publish
    original_slot = dispatch_worker.slot
    original_cli_run = lanes.run
    from providers import Redactor
    redact_cli = Redactor(root, "")
    def cli_run(argv, **kwargs):
        try:
            result = original_cli_run(argv, **kwargs)
        except BaseException as error:
            worker_runtime["cli_outputs"].append(capture_cli_output(folder, error=error,
                redact=lambda text: redact_cli(dispatch_worker.redact(text))))
            atomic_json(folder / "RUNTIME.json", worker_runtime)
            raise
        worker_runtime["cli_outputs"].append(capture_cli_output(folder, result=result,
            redact=lambda text: redact_cli(dispatch_worker.redact(text))))
        atomic_json(folder / "RUNTIME.json", worker_runtime)
        return result
    def publish(row, cwd, folder, projects):
        publication = original_publish(row, cwd, folder, projects)
        if publication:
            # The real guard has already verified the accepted commit at the
            # local remote. Present only the destination actually exercised.
            publication.update(transport=SCOPE, url=transport.local_remote(publication["repo"]).as_uri())
        return publication
    def sandbox(argv, workspace, read_only=False):
        argv = explicit_cursor_model(argv)
        worker_runtime["model_invocations"].append(dict(executable=str(argv[0]),
            model=argv[argv.index("--model") + 1] if "--model" in argv else "OpenAI Codex CLI"))
        command = original_sandbox(argv, workspace, read_only=read_only)
        require(command[:2] == ["/usr/bin/sandbox-exec", "-p"], "Missing macOS worker boundary")
        command[2] += extra_policy(manifest)
        return command
    def checks(argv, **kwargs):
        # The cross-project gate can execute package scripts, but cannot write
        # back to source repositories or server-owned local publication state.
        return original_checks(["/usr/bin/sandbox-exec", "-p", "(version 1) (allow default)" +
                                extra_policy(manifest), *argv], **kwargs)
    with patch.object(dispatch_worker, "ROOT", private), \
         patch.object(dispatch_worker, "CONDUCTOR", private / "conductor"), \
         patch.object(dispatch_worker, "project_catalog", return_value=manifest["projects"]), \
         patch.object(draft_publish, "run", side_effect=transport.run), \
         patch.object(draft_publish, "publish", side_effect=publish), \
         patch.object(lanes, "sandbox_command", side_effect=sandbox), \
         patch.object(dispatch_worker, "slot", side_effect=lambda lane: ready_worker_slot(lane, original_slot)), \
         patch.object(lanes, "run", side_effect=cli_run), \
         patch.object(mini_worker, "run", side_effect=checks):
        code = dispatch_worker.execute(identifier, token)
    atomic_json(folder / "RUNTIME.json", worker_runtime)
    row = dispatch_worker.task_queue.tasks(private)[identifier]
    if row["status"] == "succeeded" and row.get("publication"):
        # Keep the application's original object intact; record the transport
        # separately so a GitHub-shaped display URL is never claimed verified.
        publication = row["publication"]
        record = dict(job_id=identifier, scope=SCOPE, publication=publication,
                      local_remote=str(transport.local_remote(publication["repo"])),
                      actual_ref="refs/heads/" + publication["branch"],
                      actual_sha=git(transport.local_remote(publication["repo"]),
                                     "rev-parse", "refs/heads/" + publication["branch"]),
                      github_receipt=False)
        if row.get("draft_pr"):
            record["draft_pr"] = artifact(transport.receipt_path(publication["repo"], publication["branch"]))
        atomic_json(private / "conductor/state/task-runs" / identifier / "LOCAL-PUBLICATION.json", record)
    return code


def verify_job(row, manifest, artifacts):
    from result_acceptance import check_answer
    from mini_worker import coding_commands
    private = Path(manifest["private_root"])
    runtime = json.loads(checked_artifact(artifacts["runtime"], private).read_text())
    verify_imports(runtime["imports"], WORKER_IMPORTS, Path(manifest["candidate"]))
    require(runtime["shared_root"] == manifest["real_root"] and runtime["shared_meter"] == manifest["shared_meter"] and
            runtime["shared_locks"] == manifest["shared_locks"], "Worker used an isolated budget or lease")
    require(bool(runtime["model_invocations"]), "Private job has no actual CLI invocation receipt")
    require(len(runtime.get("cli_outputs", [])) == len(runtime["model_invocations"]),
            "Private CLI transport evidence is incomplete")
    for output in runtime["cli_outputs"]:
        receipt = json.loads(checked_artifact(output, private).read_text())
        require(receipt.get("transport") == "actual-cli-output" and receipt.get("exit") == 0 and
                not receipt.get("error"), "Private CLI transport did not succeed")
    for invocation in runtime["model_invocations"]:
        expected_model = CURSOR_MODEL if row["worker"] == "cursor" else "OpenAI Codex CLI"
        require(invocation["model"] == expected_model and
                Path(invocation["executable"]).name == ("cursor-agent" if row["worker"] == "cursor" else "codex"),
                "Private CLI invocation did not use an explicit allowed provider/model")
    require(row["status"] == "succeeded" and row.get("execution_started_at"), "Private job did not complete")
    require(row["kind"] == "coding" and row["worker"] in ("codex", "cursor"), "Unexpected private worker assignment")
    require(row["worker"] == row["requested_worker"], "Private replay silently changed the requested worker")
    check_answer(row["prompt"], row["result"], kind=row["kind"])
    require(row.get("acceptance", {}).get("accepted") is True, "Private result lacks real acceptance")
    require(hashlib.sha256(row["result"].encode()).hexdigest() == row["result_sha256"] ==
            row["acceptance"]["result_sha256"], "Private accepted result hash mismatch")
    cwd = Path(row["worktree"]).resolve()
    require(cwd.is_relative_to(private / "workspaces") and row["branch"] == "draft/" + row["id"],
            "Private coding checkout escaped its task")
    require(git(cwd, "branch", "--show-current") == row["branch"] and not git(cwd, "status", "--porcelain"),
            "Private result must remain committed on its task draft")
    proof = row["acceptance"].get("coding_evidence", {})
    require(proof.get("sha") == git(cwd, "rev-parse", "HEAD"), "Coding acceptance is not bound to HEAD")
    code_path = checked_artifact(artifacts["coding"], private)
    code = json.loads(code_path.read_text())
    require(code["sha"] == proof["sha"] and code["base_sha"] == proof["base_sha"], "Coding proof identity mismatch")
    require(code["changed_paths"] == git(cwd, "diff", "--name-only", proof["base_sha"], proof["sha"]).splitlines(),
            "Coding changed paths no longer match committed evidence")
    require(code["diff"] == git(cwd, "diff", "--no-ext-diff", proof["base_sha"], proof["sha"]),
            "Coding accepted diff changed")
    require(checked_artifact(artifacts["result"], private).read_text().strip() == row["result"].strip(),
            "Saved private result changed")
    checked_artifact(artifacts["prompt"], private)
    required = coding_commands(row["project"])
    if required:
        validation = proof.get("validation") or {}
        require(validation.get("all_pass") is True and validation["sha"] == proof["sha"] and
                validation["started_at"] >= row["execution_started_at"], "Fresh required coding validation missing")
        require([check["command"] for check in validation["checks"]] == required, "Required coding checks omitted")
        require(len(artifacts.get("validation_logs", [])) == len(required), "Coding validation logs omitted")
        for check, saved in zip(validation["checks"], artifacts["validation_logs"]):
            log = checked_artifact(saved, private)
            require(check["exit"] == 0 and str(log) == check["log"] and digest(log) == check["sha256"],
                    "Required coding check failed or log changed")
    publication = row.get("publication") or {}
    require(publication.get("sha") == proof["sha"] and publication.get("branch") == row["branch"],
            "Private draft publication did not match accepted commit")
    name = row["publish_project"]
    require(name in manifest["sources"] and publication["repo"] == manifest["projects"][name]["remote"],
            "Private job used an unapproved publication destination")
    local = json.loads(checked_artifact(artifacts["publication"], private).read_text())
    remote = Path(manifest["sources"][name]["remote"])
    require(publication.get("transport") == SCOPE and publication.get("url") == remote.as_uri(),
            "Private publication must identify the actual local transport")
    require(local["scope"] == SCOPE and local["github_receipt"] is False and local["job_id"] == row["id"] and
            local["publication"] == publication and local["local_remote"] == str(remote) and
            local["actual_ref"] == "refs/heads/" + row["branch"] and local["actual_sha"] == proof["sha"] and
            git(remote, "rev-parse", local["actual_ref"]) == proof["sha"], "Local draft ref proof mismatch")
    if row.get("draft_pr"):
        pr_path = checked_artifact(local["draft_pr"], private)
        pr = json.loads(pr_path.read_text())
        require(pr["transport"] == "local-draft-pr-adapter" and pr["isDraft"] is True and
                pr["headRefOid"] == proof["sha"] and pr["remote"] == str(remote) and
                pr["branch"] == row["branch"] and pr["url"] == pr_path.as_uri() == publication["pr_url"],
                "Private draft PR proof mismatch")
        checked_artifact(pr["body"], private)


def verify_proof(path: Path, candidate: Path, expected_sessions: list) -> dict:
    """Revalidate private artifacts and real terminal jobs before/after activation."""
    from integration_rubric import check_reply, style_errors
    from task_dispatch import task_queue
    path, candidate = Path(path).resolve(), Path(candidate).resolve()
    proof = json.loads(path.read_text())
    require(proof.get("scope") == SCOPE and proof.get("all_pass") is True, "Private replay did not pass")
    sha = git(candidate, "rev-parse", "HEAD")
    require(not git(candidate, "status", "--porcelain"), "Candidate changed after private replay")
    require(proof["sha"] == sha and Path(proof["candidate"]) == candidate, "Private replay SHA mismatch")
    private = Path(proof["private_root"]).resolve(strict=True)
    manifest = json.loads(checked_artifact(proof["manifest"], private).read_text())
    require(manifest["sha"] == sha and Path(manifest["candidate"]) == candidate and
            manifest["private_root"] == str(private) and manifest["scope"] == SCOPE,
            "Private manifest identity mismatch")
    require(set(manifest["source_files"]) == set(SOURCE_FILES), "Private harness source binding incomplete")
    for name, expected_hash in manifest["source_files"].items():
        require(digest(candidate / name) == expected_hash, "Private harness source changed: " + name)
    require(manifest["shared_meter"] == str(Path(manifest["real_root"]) / "conductor/ledger") and
            manifest["shared_locks"] == str(Path(manifest["real_root"]) / "conductor/locks"),
            "Private replay must retain the real meter and shared locks")
    require(proof["version"]["sha"] == sha and proof["final_version"]["sha"] == sha,
            "Private authenticated version mismatch")
    verify_imports(proof["imports"], CHAT_IMPORTS, candidate)
    for entry in proof["free_space"]:
        require(entry["minimum_free_bytes"] >= 5 * 1024**3, "Private replay crossed the disk floor")
    queue_path = checked_artifact(proof["queue"], private)
    require(queue_path == private / "conductor/state/queue.jsonl", "Wrong private queue artifact")
    jobs = task_queue.tasks(private)
    expected = private_sessions(expected_sessions)
    require([s["source_id"] for s in proof["sessions"]] == [s["source_id"] for s in expected],
            "Private replay source sessions changed")
    dispatched, turns = [], 0
    for observed, source in zip(proof["sessions"], expected):
        require(len(observed["turns"]) == len(source["exchanges"]), "Private replay omitted a turn")
        session = json.loads(checked_artifact(observed["saved_session"], private).read_text())
        require(session["id"] == observed["replay_id"], "Private saved session identity mismatch")
        require([m["content"] for m in session["messages"] if m["role"] == "user"] ==
                [x["message"] for x in source["exchanges"]], "Private replay changed the original messages")
        for receipt, exchange in zip(observed["turns"], source["exchanges"]):
            turn = json.loads(checked_artifact(receipt, private).read_text())
            require(turn["message"] == exchange["message"] and turn["expected"] == exchange["expected"],
                    "Private replay changed a rubric expectation")
            errors = check_reply(turn["answer"], exchange, observed["replay_id"], turn["started"],
                                 turn["before"], turn["after"], turn["jobs"])
            require(not errors, "Private reply rubric: " + "; ".join(errors))
            answer = turn["answer"]
            saved = next(m for m in session["messages"] if m.get("request_id") == answer["request_id"] and
                         m["role"] == "assistant")
            require(saved["id"] == answer["id"] and saved["content"] == answer["content"] and
                    saved.get("status_observation") == answer.get("status_observation"),
                    "Private dispatch/status reply was rewritten after completion")
            dispatched.extend(answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else []))
            turns += 1
        for message in session["messages"]:
            if message.get("task_status"):
                require(not style_errors(message["content"], 1 + len(message.get("task_ids", []))),
                        "Private completion reply failed style checks")
    require(turns == 10 and len(dispatched) == 6 and len(set(dispatched)) == 6 and
            set(dispatched) == set(jobs) == set(proof["jobs"]), "Private replay needs all ten turns and six jobs")
    require(len({jobs[job]["worktree"] for job in jobs}) == 6, "Private jobs reused a coding worktree")
    for identifier, row in jobs.items():
        verify_job(row, manifest, proof["jobs"][identifier])
    for name, source in manifest["sources"].items():
        require(source_state(Path(source["path"])) == source["before"], "Original project changed: " + name)
        require(git(source["clone"], "rev-parse", "HEAD") == source["sha"] and
                not git(source["clone"], "status", "--porcelain"), "Private source base changed")
        refs = git(source["remote"], "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
        expected_refs = sorted("refs/heads/" + row["branch"] + " " + row["publication"]["sha"]
                               for row in jobs.values() if row["publish_project"] == name)
        require(sorted(refs) == expected_refs, "Unexpected private publication ref")
    return dict(all_pass=True, sha=sha, captured_turns=10, passed_turns=10, task_count=6,
                source_ids=[s["source_id"] for s in expected], scope=SCOPE, path=str(path), sha256=digest(path))


def run_replay(root, candidate, output, timeout=1800):
    require(os.environ.get("BOB_ROOT") == str(root), "Launch with the real BOB_ROOT for shared metering")
    deadline = time.monotonic() + timeout
    manifest_path = prepare(root, candidate, output)
    manifest = json.loads(manifest_path.read_text())
    private = Path(manifest["private_root"])
    from app import Chat, Server
    from providers import run as provider_run
    from live_redeploy_check import Client
    from live_status_snapshot import build_live_status_snapshot
    from integration_rubric import check_reply
    from task_dispatch import task_queue
    from command import kill_group
    import state
    require(state.ROOT == root, "Harness imported a private budget/state root")
    require(git(candidate, "rev-parse", "HEAD") == manifest["sha"], "Candidate changed during preparation")
    evidence = dict(scope=SCOPE, sha=manifest["sha"], candidate=str(candidate), private_root=str(private),
                    manifest=artifact(manifest_path), all_pass=False, sessions=[], jobs={},
                    imports=imported_modules(CHAT_IMPORTS),
                    free_space=list(manifest["free_space"]), started_at=time.time())
    atomic_json(output, evidence, exclusive=True)
    def save(stage):
        evidence["free_space"].append(require_disk_space(root, candidate, stage))
        # Keep periodic disk receipts bounded; initial/per-stage checks remain.
        if len(evidence["free_space"]) > 40:
            evidence["free_space"] = evidence["free_space"][:15] + evidence["free_space"][-25:]
        atomic_json(output, evidence)
    def private_provider_run(argv, **kwargs):
        return provider_run(explicit_cursor_model(argv), **kwargs)
    chat = Chat(private / "conductor/webchat", private,
                private_context_providers(root, private, runner=private_provider_run))
    server = Server(("127.0.0.1", 0), chat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = Client("http://127.0.0.1:" + str(server.server_port), chat.folder / ".password")
    processes = {}
    try:
        client.login()
        evidence["version"] = client.call("/api/version")
        require(evidence["version"]["sha"] == manifest["sha"], "Private listener is not the candidate SHA")
        save("ISOLATED_HTTP_READY")
        for source in private_sessions():
            cid = client.new()
            observed = dict(source_id=source["source_id"], replay_id=cid, turns=[])
            evidence["sessions"].append(observed)
            for index, exchange in enumerate(source["exchanges"]):
                require(time.monotonic() < deadline, "Private replay timeout")
                before = build_live_status_snapshot(private)
                started = time.time()
                _, answer = client.submit(cid, exchange["message"])
                after = build_live_status_snapshot(private)
                rows = task_queue.tasks(private)
                errors = check_reply(answer, exchange, cid, started, before, after, rows)
                require(not errors, "Private turn rubric: " + "; ".join(errors))
                ids = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
                api_jobs = {r["id"]: r for r in client.call("/api/jobs")["dispatch"]}
                require(all(identifier in api_jobs for identifier in ids), "Private Jobs API omitted a receipt")
                saved = private / (source["source_id"][:8] + "-turn-" + str(index + 1) + ".json")
                atomic_json(saved, dict(message=exchange["message"], expected=exchange["expected"], answer=answer,
                                        started=started, before={"captured_at": before["captured_at"]},
                                        after={"captured_at": after["captured_at"]}, jobs={i: rows[i] for i in ids}))
                observed["turns"].append(artifact(saved))
                save("ISOLATED_TURN")
        last_save = 0
        while True:
            require(time.monotonic() < deadline, "Private replay timed out waiting for all six real jobs")
            rows = task_queue.tasks(private)
            require(len(rows) == 6, "Private replay must dispatch exactly six coding jobs")
            for identifier, row in rows.items():
                require(row["status"] not in ("failed", "cancelled"), "Private job failed: " + identifier + " " + str(row.get("error")))
            for identifier, (process, log) in list(processes.items()):
                if process.poll() is not None:
                    log.close()
                    del processes[identifier]
                    require(rows[identifier]["status"] not in task_queue.ACTIVE,
                            "Private worker exited before a fenced closeout: " + identifier)
            if all(row["status"] == "succeeded" for row in rows.values()) and not processes:
                break
            busy_workers = {rows[identifier]["worker"] for identifier in processes}
            for worker_name in ("codex", "cursor"):
                if worker_name in busy_workers:
                    continue
                claim, readiness = claim_when_ready(private, worker_name)
                evidence.setdefault("lane_readiness", {})[worker_name] = readiness
                if claim:
                    argv = [sys.executable, str(Path(__file__).resolve()), "--worker-manifest", str(manifest_path),
                            "--job", claim["id"], "--token", claim["claim_token"]]
                    log = (private / (claim["id"] + "-worker.log")).open("a")
                    process = subprocess.Popen(argv, cwd=candidate, env=dict(os.environ, BOB_ROOT=str(root)),
                                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    processes[claim["id"]] = (process, log)
            if time.monotonic() - last_save > 20:
                save("ISOLATED_EXECUTION")
                last_save = time.monotonic()
                print("Private replay: " + ", ".join(row["title"] + "=" + row["status"] for row in rows.values()), flush=True)
            time.sleep(1)
        for row in rows.values():
            folder = private / "conductor/state/task-runs" / row["id"]
            evidence["jobs"][row["id"]] = dict(result=artifact(folder / "RESULT.md"), prompt=artifact(folder / "prompt.txt"),
                runtime=artifact(folder / "RUNTIME.json"),
                coding=artifact(folder / "CODING-EVIDENCE.json"), publication=artifact(folder / "LOCAL-PUBLICATION.json"),
                validation_logs=[artifact(check["log"]) for check in (row["acceptance"]["coding_evidence"].get("validation") or {}).get("checks", [])])
        for observed in evidence["sessions"]:
            client.call("/api/conversations/" + observed["replay_id"])
            observed["saved_session"] = artifact(chat.state / (observed["replay_id"] + ".json"))
        evidence.update(queue=artifact(private / "conductor/state/queue.jsonl"), final_version=client.call("/api/version"),
                        all_pass=True, finished_at=time.time())
        save("ISOLATED_FINAL")
        verified = verify_proof(output, candidate, private_sessions())
        print(json.dumps(verified), flush=True)
        return 0
    except BaseException as error:
        task_queue.cancel_replay(private, {s["replay_id"] for s in evidence["sessions"]}, "Private release replay failed")
        evidence.update(all_pass=False, failure=str(error), finished_at=time.time())
        atomic_json(output, evidence)
        raise
    finally:
        for process, log in processes.values():
            if process.poll() is None:
                kill_group(process)
            log.close()
        server.shutdown()
        server.server_close()
        chat.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--candidate", type=Path, default=CODE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--worker-manifest", type=Path)
    parser.add_argument("--job")
    parser.add_argument("--token")
    args = parser.parse_args(argv)
    os.umask(0o077)
    if args.worker_manifest:
        return worker(args.worker_manifest, args.job, args.token)
    if not args.root or not args.output:
        parser.error("--root and --output are required")
    root = args.root.resolve()
    os.environ["BOB_ROOT"] = str(root)
    previous = {}
    def interrupted(signum, frame):
        raise RuntimeError("Private replay interrupted: " + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.signal(signum, interrupted)
    try:
        return run_replay(root, args.candidate.resolve(), args.output.resolve(), args.timeout)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
