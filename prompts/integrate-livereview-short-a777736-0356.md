# LIVE Gemini+MiniMax review — integrate tip a777736 (0356)

You are reviewing Web Bob integrate tip for LIVE gate before deploy.

**Tip:** `a777736b3f0a37c82b0c4c62be8c91117c4c9881` on `draft/webbob-integrate-2057`
**Offline:** INTEGRATE-FIXED-0256 RESULT READY — 342 webchat / 131 services / 96 evals all green.
**Prior LIVE on 199eb19:** Gemini FAIL + MiniMax PASS (does NOT cover this tip).
**Production still:** dff84e3 after prior integrate deploy rollback.

## Scope to verify
1. API workers live-dispatch under parked holds (Barker/Wildflower) — Gemini audit + MiniMax test-writing as real workers with reports.
2. Production checkout identity: build_info.CODE_ROOT, Git-root resolution, invalid-marker rejection, nested-code handling (see FIXED-0256).
3. Rubric deployed_checkout / screen fixture vs fallback: attempt2 fixture verifies deploy-only screen unverified with no project/repo/task; Turn 1 still creates API jobs under holds.
4. Session-freeze honesty — no empty "work started" promises.
5. No force-push; draft-only; do not deploy.

## Verdict required
End with exactly one line: VERDICT: PASS or VERDICT: FAIL
If FAIL, list CRITICAL/HIGH with file:line evidence. Explicitly say whether build_info.py / worker_assignment.py evidence resolves prior Gemini CRITICAL claims from 199eb19 review.

## Offline READY summary (INTEGRATE-FIXED-0256)
# INTEGRATE-FIXED-0256

RESULT: READY

New tip: `a777736b3f0a37c82b0c4c62be8c91117c4c9881`  
Branch: `draft/webbob-integrate-2057`  
Base: `199eb193396802bbbf899292e48cd04a55f9c57e`  
Completed UTC: 2026-09-28T08:17:08.328671+00:00

Regular push to `brain/draft/webbob-integrate-2057` succeeded:
`199eb19..a777736`. The remote tip equals HEAD and the candidate working tree
is clean. This is an offline READY result; no deployment was attempted.

Gemini findings were investigated against the reviewed commit and the running
code layout, with these results:

| Finding | Diagnosis and resolution |
| --- | --- |
| CRITICAL 1: unverifiable `build_info` dependency | The missing-source claim was a review-evidence gap. `webchat/build_info.py` was already tracked at `199eb19` (blob `ec875bbde21864ae093bff8ea9dab7550e1e12ad`), introduced by `096693f`. Its `CODE_ROOT` comes from resolved `__file__`, independent of persistent data and generated manifests. The related `.git.exists()` check was genuinely too weak: invalid Git markers could authorize jobs. It now resolves the Git root and requires the running code's identity module as a committed blob. API report prompts explicitly request `webchat/build_info.py` as evidence. |
| CRITICAL 2: deploy screen contradicts fallback | The claimed contradiction was false. A screen alone never satisfied the planner's project/repository checks. The attempt2 fixture now explicitly verifies the real collector returns only `lane-integrate-deploy-0204`, unverified, with no project, repo, task, job ID or worker, and no queued/claimed source jobs or running workers. Turn 1 still creates Gemini `audit` and MiniMax `test-writing` jobs under parked holds. |
| HIGH 1–2: tests reuse `CODE_ROOT` | Valid evidence concern, with no mispointed root in this worktree. Tests now independently compare the module, test-file location and Git root, and verify the module is committed. Normal repositories and linked worktrees with `.git` files are covered. |
| HIGH 3: relative pins rejected | False defect for this deployment contract. Deployment resolves candidate paths before writing both pins; current production pins are also absolute. Relative paths remain rejected because service working directories can differ. Absolute symlink aliases are accepted and tested. |
| HIGH 4: code nested below Git root | Real layout limitation, though this production candidate is itself a Git worktree root. Committed nested code now resolves its Git root correctly. Pins continue to select the running code directory. Untracked or staged-only nested archives cannot borrow a parent repository's identity. |

The old assignment code failed the new invalid-marker and nested-code
regressions before the fix (`red-checkout-regressions.log`). Both now pass.
`git_checkout_root` is shared by release identity and the assignment fallback;
Git failures, timeouts, inherited Git location overrides, deleted/linked
identity files, rollback copies and incorrect pins are covered. Missing pins
are rejected before any Git subprocess is needed. The pin contract and
screen/fallback distinction are documented in `webchat/README.md`.

| Validation on the new tip | Result |
| --- | --- |
| Full webchat unittest discovery | 342/342 passed |
| Full services unittest discovery | 131/131 passed |
| Bob parity/integration evals | 96/96 passed |
| Quiet-hours and job-results JavaScript tests | Passed |
| app.js syntax, 123 tracked Python files compiled, whitespace | Passed |
| Read-only current-session capture check | All 19 asks passed |

The evals retain all 19 captured asks in order across three conditions: seeded
work, an identified project lane without a worker, and the attempt2 deploy-only
screen with matching pins and parked Barker/Wildflower holds. The services
regression uses `deploy_integrate.submit` through an isolated HTTP adapter,
then real chat, durable queue, scheduler, API-worker, metered transport and
report-saving code. It checks both exact API models, execution timestamps,
report hashes, original receipts, unchanged holds, and inclusion of the tracked
`build_info.py` in both provider payloads. HTTP provider responses, lane health
and semantic acceptance are mocked; these checks do not prove live provider
execution or a live reviewer PASS.

Full suites ran after the commit using isolated BOB_ROOT directories and
canonical temporary paths outside the checkout, with provider credentials
removed. All 362 tracked files match the tested commit. The capture fixture
and all 792 conversation files retain their original bytes. Only the separate
`provider-health.json` runtime cache changed during this window. This repair
did not write any `conductor/webchat/sessions/*.json` file. Barker and Wildflower
remain parked; no empty work-started promises were introduced.

Live deployment pins remain unchanged and still select the rollback whose
manifest is `dff84e37169b30014ff0f48502b8cc66542cf737`.
`webchat/evidence/integrate-tests.json` is refreshed with `sha==HEAD`,
`suite_exit=eval_exit=0`, and `eval.passed=eval.total=96`.

Evidence: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/reviews/integrate-fixed-0256`. The directory contains the red regression,
diagnosis, full suite/eval logs and counts, tracked-source/session hashes,
preservation checks, regular-push output, remote-tip verification and
`validation.json`.

LIVE Gemini + MiniMax MUST be re-run on `a777736b3f0a37c82b0c4c62be8c91117c4c9881` before deploy.
The prior MiniMax PASS and Gemini FAIL on `199eb19` do not cover this new tip.
A later authorized deployment must also pass the real replay/execution rubric.
The review source bundle should include `webchat/build_info.py`,
`webchat/worker_assignment.py`, `webchat/worker_evidence.py`,
`webchat/integration_rubric.py`, `webchat/test_build_info.py`,
`webchat/test_integrate_2057.py`, `services/test_api_workers.py`,
`webchat/deploy_parity.py`, and this report to avoid repeating the omitted-source
ambiguity.

No deployment, live review, service restart, merge, undraft, force-push,
Jeff notification, or Grok/xAI call was performed.


## Source bundle (from tip a777736)
### FILE: webchat/build_info.py
```python
"""Identity of this code release, independent of persistent chat/brain data."""
import html
import json
import os
import re
import subprocess
from pathlib import Path

# This tracked module lives in <running code>/webchat, including Git worktrees.
# Persistent BOB_ROOT data and deployment manifests never choose its location.
CODE_ROOT = Path(__file__).resolve().parents[1]
STATIC = CODE_ROOT / "webchat/static"


def _git(code_root, *args):
    # An inherited Git override must not identify another checkout as this one.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.check_output(["git", "-C", str(code_root), *args], text=True,
                                   stderr=subprocess.DEVNULL, timeout=5, env=env).strip()


def git_checkout_root(code_root=CODE_ROOT):
    """Resolve Git identity only when this code's identity module is committed.

    Supports normal checkouts, linked worktrees and tracked nested layouts.
    An archive under an unrelated parent repository cannot borrow its identity.
    """
    try:
        code_root = Path(code_root).resolve(strict=True)
        module = code_root / "webchat/build_info.py"
        if not module.is_file() or module.resolve(strict=True) != module:
            return None
        checkout = Path(_git(code_root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        relative = module.relative_to(checkout).as_posix()
        if _git(code_root, "cat-file", "-t", "HEAD:" + relative) != "blob":
            return None
        return checkout
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return None


def load_build(code_root=CODE_ROOT):
    manifest = code_root / "webbob-build.json"
    if manifest.is_file():
        value = json.loads(manifest.read_text())
        sha, built_at = value["sha"], value["built_at"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid Web Bob release SHA")
    elif git_checkout_root(code_root) is not None:
        sha, built_at = _git(code_root, "rev-parse", "HEAD"), _git(code_root, "show", "-s", "--format=%cI", "HEAD")
    else:
        # Do not walk up to another project's repository or read BOB-STATE.
        sha, built_at = "unknown", "unknown"
    return dict(name="Web Bob", sha=sha, short_sha=sha[:7], built_at=built_at)


BUILD = load_build()
VERSION_QUESTION = re.compile(
    r"\b(?:what|which)\s+(?:version(?:/build)?|build(?:\s+number)?|sha|commit)\s+"
    r"(?:are you|is (?:this|web\s*bob)|am i (?:using|running))\b|"
    r"\b(?:what(?:['’]s| is)|show(?: me)?)\s+(?:your|web\s*bob['’]s)\s+"
    r"(?:version|build(?:\s+number)?|sha|commit)\b|"
    r"^(?:(?:your|web\s*bob)\s+)?(?:version|build(?:\s+number)?|build/sha)[?!. ]*$", re.I)


def render_page(name):
    value = (STATIC / name).read_text()
    for key, replacement in (("__WEBBOB_SHA__", BUILD["short_sha"]),
                             ("__WEBBOB_BUILT_AT__", BUILD["built_at"])):
        value = value.replace(key, html.escape(replacement, quote=True))
    return value

```

### FILE: webchat/worker_assignment.py
```python
"""Turn requests to use LLMs on ongoing work into durable, scoped assignments."""
import json
import re
from pathlib import Path

import task_queue
from api_tasks import ROLES
from build_info import CODE_ROOT, git_checkout_root
from chat_intent import blocked_scopes, command, project_targets, state_for
from live_status_snapshot import observe_work

NAMES = r"(?:gemini|minimax|codex|claude|cursor(?:-agent)?|grok|xai|xAI)"
DIRECTIVE = re.compile(
    r"^(?:remember\s*[:,]?\s*(?:that\s+)?(?:(?:you|we)\s+can\s+|to\s+)?|(?:you|we)\s+can\s+)?"
    r"(?:also\s+)?(?:use|assign|put|have|get|delegate\s+to)\s+(?P<names>" + NAMES +
    r"(?:\s*(?:,|&|and)\s*(?:and\s+)?" + NAMES + r")*)\b(?P<rest>.*)$", re.I | re.S)
ONGOING = re.compile(r"\b(?:ongoing|current|existing|active|running|queued)\b.{0,35}\b(?:jobs?|tasks?|work|projects?)\b|"
                     r"\b(?:jobs?|tasks?|work|projects?)\b.{0,30}\b(?:ongoing|underway|running)\b|"
                     r"\b(?:for|on|with)\s+(?:these|those|our|the)\s+(?:jobs?|tasks?|work)\b", re.I)


def requested_workers(text, conversation=None):
    cleaned = command(text)
    if re.match(r"^(?:don't|do not|never|stop|hold)\b", cleaned, re.I):
        return None
    # A follow-up references the last explicit worker request, not arbitrary
    # names from a model answer or provider-health metadata.
    followup = re.search(r"\b(?:add|assign|queue|give)\s+(?:some |more |new )?(?:work|jobs?|tasks?)\s+(?:for|to)\s+(?:them|those (?:LLMs|workers))\b|"
                         r"\b(?:want|need)\s+them\s+(?:workout|working|to work|busy)\b|"
                         r"\b(?:put|get|keep)\s+them\s+(?:to work|working|busy)\b", cleaned, re.I)
    if followup:
        names = (conversation or {}).get("assignment_workers")
        if not names:
            for message in reversed((conversation or {}).get("messages", [])):
                if message.get("role") == "user" and message.get("content") != text:
                    names = requested_workers(message.get("content", ""))
                    if names:
                        break
        if names:
            return list(names)
    all_workers = re.match(r"^(?:use|assign|put|get|keep)\s+all\s+(?:the\s+)?(?:LLMs|models|workers)\b", cleaned, re.I)
    if all_workers and (ONGOING.search(cleaned) or re.search(r"\b(?:to work|busy|working)\b", cleaned, re.I)):
        return list(task_queue.MODEL_WORKERS)
    match = DIRECTIVE.match(cleaned)
    reminder = re.match(r"^(?:remember|you can|we can)\b", cleaned, re.I)
    if not match or not (ONGOING.search(match["rest"]) or (reminder and re.fullmatch(r"\s*(?:too|also)?[.!]*", match["rest"], re.I))):
        return None
    return list(dict.fromkeys(name.lower().replace("cursor-agent", "cursor")
                              for name in re.findall(NAMES, match["names"], re.I)))


def issue_followup(root, conversation, text):
    if not re.fullmatch(r"if you find (?:any )?(?:issues|bugs)[, ]+(?:please )?fix them[.!]*", command(text), re.I):
        return None
    previous = next((m["dispatch_intent"] for m in reversed(conversation["messages"][:-2])
                     if m.get("dispatch_intent", {}).get("worker_assignment")), None)
    if not previous or not previous.get("assignment_projects"):
        return None
    project = previous["assignment_projects"][0]
    return ("Fix verified issues in " + project + "\nInspect the ongoing work and available review reports, "
            "reproduce a concrete issue, implement one bounded fix if warranted, and run relevant tests. "
            "Report evidence if no fix is needed. Work in your assigned draft worktree; never deploy or merge.")


def deployed_project_context(root):
    """A pinned checkout can supply API evidence, never proof of ongoing work."""
    # Deployments can have no active jobs and no identifiable project screen.
    # Both services must select this running checkout; an arbitrary/stale pin
    # or a rollback copy without Git evidence is not enough to assign a report.
    try:
        for name in ("webchat", "dispatch"):
            value = (root / "conductor/state" / (name + "-code-root")).read_text().strip()
            path = Path(value)
            if not path.is_absolute() or path.resolve(strict=True) != CODE_ROOT:
                return None
    except (OSError, ValueError, RuntimeError):
        return None
    if git_checkout_root(CODE_ROOT) is None:
        return None
    return dict(id=None, project="Web Bob", context="project context", prompt=(
        "The Web Bob checkout is selected by matching deployment pins for this server and its dispatcher; "
        "no current task or worker execution is confirmed. Inspect the supplied repository snapshot for "
        "concrete dispatch findings and regression test drafts, including webchat/build_info.py, "
        "webchat/worker_assignment.py, "
        "webchat/task_dispatch.py, state/task_queue.py and services/dispatch_worker.py. "
        "Do not infer active work, progress or results from deployment metadata."))


def plan(root, conversation, text, workers):
    for worker in workers:
        task_queue.worker_name(worker)  # Reject Grok/xAI before any queue write.
    observed = observe_work(root)
    state = state_for(conversation)
    targets = project_targets(text, state)
    candidates = []
    for row in observed["records"].values():
        if (row.get("status") or row.get("state")) not in ("queued", "claimed", "launched", "running"):
            continue
        if row.get("source_job_id") or (row.get("kind") in ("audit", "test-writing", "planning", "review", "research", "eval-grading")):
            continue  # Never recursively create report jobs about report jobs.
        prompt = row.get("prompt") or row.get("title") or row.get("project")
        if not prompt:
            continue
        names = project_targets(row.get("project") or prompt, state)
        if targets and not any(name in targets for name in names):
            continue
        if blocked_scopes(state, names):
            continue
        candidates.append(dict(id=row["job_id"], prompt=prompt,
                               project=", ".join(names) or "Web Bob"))
    # Some ongoing jobs are external CLI workers, observed outside the journal.
    known = {row["id"] for row in candidates}
    for row in observed["work"]:
        if row["state"] != "running" or row.get("job_id") in known or not (row.get("task") or row.get("title")) or not row.get("project"):
            continue
        if row.get("job_id") and observed["records"].get(row["job_id"], {}).get("kind") in ("audit", "test-writing", "planning", "review", "research", "eval-grading"):
            continue
        if targets and row["project"] not in targets:
            continue
        if blocked_scopes(state, [row["project"]]):
            continue
        task = row.get("task") or ("Observed active lane: " + row["title"] +
                                   ". Its original task prompt was not recorded; inspect the project's current code and "
                                   "state that limitation. Do not invent the lane's exact assignment.")
        candidates.append(dict(id=None, prompt=task, project=row["project"]))
    # An open project lane can outlive its worker process. It still identifies
    # a repository for a new API report, but proves neither an ongoing task nor
    # execution. Use it only when no permitted active assignment is available;
    # never turn this limited context into a coding job or a fake source job ID.
    if not candidates and all(worker in task_queue.API_WORKERS for worker in workers):
        seen_projects = set()
        for row in observed["work"]:
            project = row.get("project")
            if (row["state"] != "unverified" or row.get("source") != "screen" or row.get("job_id")
                    or row.get("screen") not in observed.get("sessions", {})
                    or not project or not row.get("repo") or not row.get("title") or project in seen_projects):
                continue
            if (targets and project not in targets) or blocked_scopes(state, [project]):
                continue
            context = ("Observed open project lane: " + row["title"] + ". Its worker activity is unverified; "
                       "no current task is confirmed. Inspect the project's supplied repository snapshot "
                       "for concrete findings and regression test drafts. Do not infer active work, "
                       "progress or results from the lane name or historical logs.")
            candidates.append(dict(id=None, prompt=context, project=project, context="project context"))
            seen_projects.add(project)
        if not candidates and (not targets or "Web Bob" in targets) and not blocked_scopes(state, ["Web Bob"]):
            context = deployed_project_context(root)
            if context:
                candidates.append(context)
    if not candidates:
        raise ValueError("I couldn't assign those workers: there is no identifiable ongoing job permitted by the current holds. Name a project and task to start.")
    health = root / "conductor/lanes.json"
    board = json.loads(health.read_text()) if health.exists() else {}
    packages = []
    for index, worker in enumerate(workers):
        row = board.get(worker, {})
        if row.get("state") in ("needs_key", "unavailable", "budget_exhausted", "cooldown", "needs_login"):
            raise ValueError("I couldn't assign " + worker + ": " + row["state"].replace("_", " ") + ". No new assignments were queued.")
        source = candidates[index % len(candidates)]
        kind, role = ROLES.get(worker, ("analysis", "Review the ongoing task and propose next steps"))
        context = source.get("context", "ongoing task")
        # One concrete bounded package per requested worker. Keep existing
        # coders running; do not revoke a live claim or share their edit rights.
        prompt = ("Project: " + source["project"] + "\nYour independent subtask:\n" + role +
                  " for the following " + context + ". Deliver concrete findings and "
                  "an actionable plan or test drafts. Never deploy or resolve conflicts.\n" +
                  context.capitalize() + ":\n" + source["prompt"][:8000])
        packages.append(dict(worker=worker, kind=kind, title=source["project"] + " — " + role,
                             prompt=prompt, source_job_id=source["id"]))
    return packages

```

### FILE: webchat/worker_evidence.py
```python
"""Bounded, read-only task evidence for live processes and screen lanes."""
import re
import json
import time
from pathlib import Path

PROJECTS = ((r"web\s*bob|conductor", "Web Bob", "conductor"),
            (r"web\s*jam", "WebJam", "webjam"), (r"adopt\s*iq", "AdoptIQ", "AdoptIQ"),
            (r"story\s*board", "StoryBoard", "StoryBoard"),
            (r"(?:storyland[ -])?fantasy[ -]football|fantasy", "Fantasy Football", "Storyland-Fantasy-Football"),
            (r"shelf", "Shelf", "story-corner-shelf"))


def clean(text, limit=220):
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\b(?:sk-[\w-]{20,}|AIza[\w-]{25,}|gh[pousr]_[\w]{25,})\b", "[secret removed]", text)
    text = re.sub(r"(?i)\b(?:password|token|secret|api_key)\s*[:=]\s*\S+", "[secret removed]", text)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    clipped = text[:max(0, limit)]
    # Never end mid-word: a truncated raw log line should read as a phrase,
    # not garbage cut off between letters.
    if len(text) > limit and text[max(0, limit):max(0, limit) + 1] != " ":
        clipped = clipped.rsplit(" ", 1)[0]
        if " " not in text[:max(0, limit)]:
            return ""
    return clipped


def read_part(path, tail=False):
    # Prompt/log discovery never follows a link into credentials or another tree.
    if path.is_symlink() or not path.is_file():
        return ""
    try:
        with path.open("rb") as handle:
            if tail:
                handle.seek(0, 2)
                handle.seek(max(0, handle.tell() - 8192))
            return handle.read(8192).decode("utf-8", "replace")
    except OSError:
        return ""


def _tokens(value):
    return re.findall(r"[a-z]+|\d+", value.lower())


def _match_file(root, paths, screen, command):
    words = _tokens(re.sub(r"^(?:lane|svc)-", "", screen or ""))
    candidates = []
    for path in paths:
        tokens = _tokens(path.stem)
        # Explicit paths beat filename heuristics; all screen words must match.
        explicit = str(path) in command or str(path.relative_to(root)) in command
        matched = bool(words) and all(word in tokens for word in words)
        if not explicit and not matched:
            continue
        try:
            candidates.append(((int(explicit), len(words), path.stat().st_mtime), path))
        except OSError:
            continue
    return max(candidates)[1] if candidates else None


def _project(text):
    matches = [(match.start(), project, repo) for pattern, project, repo in PROJECTS
               if (match := re.search(r"\b(?:" + pattern + r")\b", text, re.I))]
    return min(matches)[1:] if matches else (None, None)


def _task(prompt):
    # Prefer the assignment to setup/rules or old quoted replies in the prompt.
    header = re.search(r"(?im)^\s*(?:task|goal|assignment)\s*:\s*(.+)", prompt)
    text = header[1] if header else prompt.splitlines()[0] if prompt else ""
    text = re.sub(r"^(?:TOP PRIORITY[.!:]?\s*)", "", text, flags=re.I)
    if re.match(r"Follow-up \d+ on [\w./-]+:", text):
        text = re.sub(r"^Follow-up \d+ on [\w./-]+:\s*", "", text)
        text = re.split(r"[;(]", text, maxsplit=1)[0]
    text = re.sub(r"^Project:\s*[^\n]+", "", text, flags=re.I)
    if not text and prompt:
        text = next((line for line in prompt.splitlines()[1:] if line.strip()), "")
    text = re.split(r"[.!?]\s", text, maxsplit=1)[0]
    if re.match(r"Improve .+: inspect the project, choose one useful bounded fix", text):
        text = text.split(":", 1)[0]
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "", text)
    if re.search(r"\b(?:read|review|audit|fix|repair|implement|build|improve|develop|test|redesign|replies|reply|status|check|plan|research|gives bad|project push|deploy|gate)\b", text, re.I):
        return clean(text, 160).strip(" .")
    return None


def _inline_prompt(command):
    """Only the live CLI's task argument, not strings in an arbitrary process."""
    command = command.replace("\\012", "\n")
    match = re.search(r"\s(?:-p|--print)\s+(.+)", command, re.S)
    if match:
        return match[1]
    match = re.search(r"\b(?:exec|review)\s+(.+)", command, re.S)
    if not match:
        return ""
    text = match[1]
    while text.startswith("-"):
        option = re.match(r"(--?[\w-]+)(?:=\S+)?\s*", text)
        if not option:
            return ""
        text = text[option.end():]
        if option[1] in ("-c", "--config", "-m", "--model", "-C", "--cd", "-s", "--sandbox", "-a", "--ask-for-approval", "-o", "--output-last-message"):
            text = re.sub(r"^(?:\"[^\"]*\"|'[^']*'|\S+)\s*", "", text)
    return text


def _log_model(path, row):
    """Accept CLI startup metadata from this execution, never model mentions in prose."""
    if not path.is_file() or path.is_symlink() or row.get("elapsed_seconds") is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    started = time.time() - row["elapsed_seconds"]
    # A reused old transcript is not evidence of this process's selected model.
    if getattr(stat, "st_birthtime", 0) < started - 5:
        return None
    head = read_part(path)
    if row.get("worker") == "codex" and head.startswith("OpenAI Codex v"):
        header = re.split(r"(?m)^user\s*$", head, maxsplit=1)[0]
        match = re.search(r"(?m)^model:\s*([\w./:-]{1,80})\s*$", header)
        return match[1] if match else None
    if row.get("worker") in ("claude", "cursor"):
        try:
            event = json.loads(head.splitlines()[0])
            model = event.get("model", "")
            if event.get("type") == "system" and event.get("subtype") == "init" and re.fullmatch(r"[\w./:-]{1,80}", model):
                return model
        except (ValueError, IndexError, AttributeError, TypeError):
            pass
    return None


def enrich_work(root, activity, records, table):
    root = Path(root)
    prompts = list((root / "logs").glob("*prompt*.txt"))
    logs = list((root / "logs").glob("*.log"))
    by_job = {row["job_id"]: row for row in records}
    for row in activity:
        record = by_job.get(row.get("job_id"), {})
        pid = row.get("pid")
        chain, seen = [], set()
        while pid in table and pid not in seen:
            seen.add(pid)
            chain.append(table[pid]["command"])
            pid = table[pid]["ppid"]
        command = "\n".join(chain)
        prompt_path = _match_file(root, prompts, row.get("screen"), command)
        log_path = _match_file(root, logs, row.get("screen"), command)
        if record:
            run_dir = root / "conductor/state/task-runs" / record["job_id"]
            if (run_dir / "prompt.txt").is_file():
                prompt_path = run_dir / "prompt.txt"
            log_path = log_path or run_dir / "worker.log"
        if log_path is None:
            log_path = root / "logs" / ((row.get("screen") or "process-" + str(row.get("pid", "observed"))) + ".log")
        if not row.get("model"):
            row["model"] = _log_model(log_path, row)
        prompt = record.get("prompt") or (read_part(prompt_path) if prompt_path else "")
        if not prompt and row.get("worker") in ("codex", "cursor", "claude"):
            prompt = _inline_prompt(table.get(row.get("pid"), {}).get("command", ""))
        # A casual reply quotes one short evidence line, not a run-on paragraph:
        # cap well under the 220-char default used for prose fields.
        tail = [clean(line, 120) for line in read_part(log_path, tail=True).splitlines() if line.strip()]
        last = tail[-1] if tail else "log has no readable lines"
        task = _task(prompt) or _task(record.get("title") or "")
        if not task and row["title"] != "Worker process" and not row.get("screen"):
            task = row["title"]
        if not task:
            task = next((_task(line) for line in reversed(tail)
                         if re.match(r"(?:Task:|Goal:|Working on |Reviewing |Fixing )", line, re.I) and _task(line)), None)
        # Resolve the project from the assignment, never from an unrelated log.
        project, repo = _project(record.get("project") or prompt[:1500] or row["title"])
        if not repo:
            project, repo = _project(row["title"])
        if not repo:
            cwd = re.search(r"\bcd\s+([^;&\n]+)", command)
            if cwd:
                project, repo = _project(cwd[1])
        explicit_repo = re.search(r"(?im)^\s*(?:repo|repository)\s*:\s*([^\n]+)", prompt)
        repo = Path(record["repo"]).name if record.get("repo") else repo
        if explicit_repo and not repo:
            repo = clean(explicit_repo[1], 100)
        row.update(project=project, repo=repo, task=task,
                   prompt_path=str(prompt_path.relative_to(root)) if prompt_path else None,
                   log_path=str(log_path.relative_to(root)), last_log_line=last)
        if task:
            row["title"] = task
    return activity

```

### FILE: webchat/integration_rubric.py
```python
"""Release rubric: actions require effects; status requires live observations."""
import copy
import json
import re
from datetime import datetime
from pathlib import Path

from dispatch_receipts import NO_DISPATCH, claims_dispatch, receipt_errors


def sessions():
    rows = json.loads(Path(__file__).with_name("fixtures").joinpath("integrate_sessions_0927.json").read_text())["sessions"]
    for session in rows:
        kinds = (["assign", "assign", "status", "status", "status", "assign", "fix", "greeting", "status"]
                 if session["source_id"].startswith("b33fac") else
                 ["missing", "status", "status", "status", "status", "projects4", "greeting", "status", "status"]
                 if session["source_id"].startswith("8126301c") else ["projects2"])
        if len(kinds) != len(session["exchanges"]):
            raise ValueError("Original session changed; review and extend the rubric before deployment")
        for exchange, kind in zip(session["exchanges"], kinds):
            exchange["expected"] = kind
    return rows


def style_errors(text, dispatch_count=0):
    prose = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    prose = re.sub(r"`webchat-[a-f0-9]{32}`", "job ID", prose)
    errors = []
    if not prose.strip():
        errors.append("empty reply")
    if len(prose.split()) > 220:
        errors.append("overlong reply")
    if len([s for s in re.split(r"[.!?](?:\s+|$)", prose) if s.strip()]) > max(4, dispatch_count):
        errors.append("too many sentences")
    if re.search(r"(?i)unknown task|task details unavailable|I['’]ll (?:focus|do better|make sure|ensure)|"
                 r"system is actively adding|ready for (?:new )?work|healthy and ready|prioritize adding work|Worker process", prose):
        errors.append("empty promise or readiness substituted for utilization")
    if re.search(r"logs/|lane-[\w-]+|\blast:|\bPID\s*[:=]|\s\|\s", prose):
        errors.append("raw diagnostic dump")
    if prose.startswith(("Yes —", "Here's the status", "I understand.")):
        errors.append("answer is not first")
    return errors


def check_reply(answer, exchange, cid, started, before, after, jobs):
    text = answer.get("content", "")
    ids = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
    errors = style_errors(text, len(ids))
    errors += receipt_errors(answer, jobs, cid, answer["request_id"], started)
    rows = [jobs[i] for i in ids if i in jobs]
    expected = exchange["expected"]
    if answer.get("status") != "done":
        errors.append("reply did not complete")
    if expected in ("assign", "fix", "projects2", "projects4"):
        if not ids or answer.get("provider") != "dispatcher":
            errors.append("work request has no real dispatch")
        for row in rows:
            label = row.get("title") or row["prompt"].splitlines()[0]
            if (label[:50] not in text or (row["requested_worker"] != "auto" and
                                          row["requested_worker"].lower() not in text.lower())):
                errors.append("receipt omits task or worker")
            if row["status"] in ("failed", "cancelled"):
                errors.append("accepted job failed: " + row["id"])
        if expected == "assign" and ([r["requested_worker"] for r in rows] != ["gemini", "minimax"] or
                                     [r["kind"] for r in rows] != ["audit", "test-writing"]):
            errors.append("Gemini/MiniMax did not receive API worker jobs")
        if expected == "fix" and (len(rows) != 1 or rows[0]["kind"] != "coding"):
            errors.append("fix request has no coding job")
        if expected.startswith("projects"):
            titles = ["WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"][:int(expected[-1])]
            if [r["title"] for r in rows] != titles:
                errors.append("named projects were not dispatched")
    else:
        if ids:
            errors.append("non-action turn dispatched work")
        if expected != "status" and text != NO_DISPATCH and claims_dispatch(text):
            errors.append("unsupported dispatch claim")
    if expected == "missing" and text != "Which projects should I work on?":
        errors.append("missing project detail was not requested")
    if expected == "greeting" and re.search(r"(?i)queue|workers|services|running", text):
        errors.append("unsolicited operations report for greeting")
    if expected == "status":
        if answer.get("provider") != "state" or re.search(r"\bready\b", text, re.I):
            errors.append("status is not an authoritative utilization report")
        for worker in ("Codex", "Claude", "Cursor", "Gemini", "MiniMax"):
            if worker not in text:
                errors.append("status omits " + worker)
        from status_observation import observation_errors
        evidence_errors = observation_errors(answer, exchange["message"], cid, started,
                                             datetime.fromisoformat(after["captured_at"]).timestamp())
        errors += evidence_errors
        if evidence_errors:
            return errors
        from reply_authority import _task_name
        observed = answer["status_observation"]["snapshot"]
        for row in observed["work"]:
            if row.get("assignment_recorded") is False:
                if "CLI activity, but no recorded task" not in text:
                    errors.append("unattributed process falsely presented as assigned work")
                continue
            if _task_name(row) not in text:
                errors.append("status omits observed task " + _task_name(row))
            if row.get("model") and row["model"] not in text:
                errors.append("status omits observed model " + row["model"])
        if text.count("running for") != observed["work_counts"]["running"]:
            errors.append("status running count disagrees with observed execution")
        for row in observed["queue_jobs"]["queued"]:
            if _task_name(row) not in text:
                errors.append("status omits waiting assignment " + _task_name(row))
    return errors


def run_eval(*, project_lane_only=False, deployed_checkout=False):
    """Run the same exact-message rubric offline against real isolated journals."""
    import tempfile
    import time
    import uuid
    from unittest.mock import patch
    from app import Chat
    from live_status_snapshot import build_live_status_snapshot
    from task_dispatch import task_queue

    class Greeting:
        def reply(self, *args):
            return dict(content="Hi Jeff!", provider="gemini", attempts=[])

    # Attempt 2 (0204) had an open deploy screen, but it identified no project,
    # repository or task. The earlier 2205 fixture also had a Web Bob lane.
    # Keep these distinct and exercise the real collector without a seed job.
    screens = ({"lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"} if deployed_checkout else
               {"lane-integrate-deploy-2205": "68531.lane-integrate-deploy-2205",
                "lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
               if project_lane_only else {})
    results = []
    with tempfile.TemporaryDirectory() as folder, \
            patch("live_status_snapshot._screen_sessions", return_value=screens), \
            patch("live_status_snapshot.process_table", return_value={}):
        root = Path(folder)
        if deployed_checkout:
            # Attempt 0204: deploy screen present, no identified project. Use the
            # same release pins written by deploy_parity.restart in production.
            from build_info import CODE_ROOT
            pins = root / "conductor/state"
            pins.mkdir(parents=True)
            for name in ("webchat", "dispatch"):
                (pins / (name + "-code-root")).write_text(str(CODE_ROOT) + "\n")
        chat = Chat(root / "conductor/webchat", root, Greeting())
        try:
            if not project_lane_only and not deployed_checkout:
                task_queue.enqueue(root, "external", "source", "Improve WebJam recording reliability", worker="codex", kind="coding", title="WebJam")
            for session_index, source in enumerate(sessions()):
                cid = chat.new_conversation()["id"]
                parked_holds = {name: dict(request_id="parked", reason="Keep parked", released_projects=[])
                                for name in ("Barker", "Wildflower")}
                if deployed_checkout:
                    chat.conversations[cid]["intent_state"]["holds"] = copy.deepcopy(parked_holds)
                    chat.save(chat.conversations[cid])
                for index, exchange in enumerate(source["exchanges"]):
                    before = build_live_status_snapshot(root)
                    started = time.time()
                    chat.submit(cid, exchange["message"], str(uuid.uuid4()))
                    thread = chat.workers.get(cid)
                    if thread:
                        thread["thread"].join(5)
                    answer = chat.get(cid)["messages"][-1]
                    errors = check_reply(answer, exchange, cid, started, before, build_live_status_snapshot(root), task_queue.tasks(root))
                    if deployed_checkout:
                        if chat.get(cid)["intent_state"]["holds"] != parked_holds:
                            errors.append("parked Barker/Wildflower holds changed")
                        if session_index == index == 0:
                            lanes = before["work"]
                            if (len(lanes) != 1 or lanes[0].get("screen") != "lane-integrate-deploy-0204"
                                    or lanes[0].get("state") != "unverified" or lanes[0].get("source") != "screen"
                                    or any(lanes[0].get(key) for key in ("project", "repo", "task", "job_id", "worker"))):
                                errors.append("attempt2 fixture must have only an unidentified deploy screen")
                            if any(before["queue_counts"][key] for key in ("queued", "claimed")) or before["work_counts"]["running"]:
                                errors.append("attempt2 fixture must start without source jobs or running workers")
                    results.append(dict(name=source["source_id"][:8] + " turn " + str(index + 1) +
                                             (" (deployed checkout, deploy screen only, parked holds)" if deployed_checkout else
                                              " (unverified project lane)" if project_lane_only else ""),
                                        pass_check=not errors, errors=errors, reply=answer["content"]))
        finally:
            chat.close()
    return results

```

### FILE: webchat/test_build_info.py
```python
"""Exercise deployed code with a different, deliberately stale data directory."""
import json
import os
import subprocess
import tempfile
import threading
import unittest
import uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app import Server
import build_info
from build_info import BUILD, CODE_ROOT, STATIC, git_checkout_root, load_build, VERSION_QUESTION
from live_redeploy_check import Client
from test_webchat import Fixture
from live_status_snapshot import _screen_sessions


class CheckoutIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        module = self.repo / "webchat/build_info.py"
        module.parent.mkdir(parents=True)
        module.write_text("# Tracked fixture identity module.\n")
        self.git("init", "-b", "main")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Fixture")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True,
                                       stderr=subprocess.STDOUT).strip()

    def test_running_identity_module_is_tracked_in_this_checkout(self):
        running = Path(__file__).resolve().parents[1]
        self.assertEqual(Path(build_info.__file__).resolve(), running / "webchat/build_info.py")
        self.assertEqual(CODE_ROOT, running)
        actual = Path(subprocess.check_output(["git", "-C", str(running), "rev-parse", "--show-toplevel"],
                                             text=True).strip()).resolve()
        self.assertEqual(git_checkout_root(), actual)
        self.assertEqual(actual, running)
        self.assertEqual(subprocess.check_output(["git", "-C", str(running), "cat-file", "-t",
                                                  "HEAD:webchat/build_info.py"], text=True).strip(), "blob")

    def test_normal_and_linked_worktrees_have_real_git_identity(self):
        self.assertTrue((self.repo / ".git").is_dir())
        self.assertEqual(git_checkout_root(self.repo), self.repo)
        linked = self.root / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        self.assertTrue((linked / ".git").is_file())
        self.assertEqual(git_checkout_root(linked), linked)
        self.assertEqual(load_build(linked)["sha"], self.git("rev-parse", "HEAD"))

    def test_nested_code_must_be_committed_to_use_the_parent_git_identity(self):
        nested = self.repo / "apps/webbob"
        module = nested / "webchat/build_info.py"
        module.parent.mkdir(parents=True)
        module.write_text("# Nested identity fixture.\n")
        self.assertIsNone(git_checkout_root(nested))
        self.assertEqual(load_build(nested)["sha"], "unknown")
        self.git("add", ".")
        self.assertIsNone(git_checkout_root(nested))
        self.git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Nested code")
        self.assertEqual(git_checkout_root(nested), self.repo)
        self.assertEqual(load_build(nested)["sha"], self.git("rev-parse", "HEAD"))

    def test_git_failures_return_no_checkout(self):
        for error in (OSError("git unavailable"), subprocess.TimeoutExpired("git", 5),
                      subprocess.CalledProcessError(128, "git")):
            with self.subTest(error=type(error).__name__), patch("build_info.subprocess.check_output", side_effect=error):
                self.assertIsNone(git_checkout_root(self.repo))

    def test_inherited_git_overrides_do_not_choose_the_repository(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "wrong-git"), "GIT_WORK_TREE": str(self.root)}):
            self.assertEqual(git_checkout_root(self.repo), self.repo)

    def test_deleted_or_linked_identity_module_cannot_supply_context(self):
        module = self.repo / "webchat/build_info.py"
        module.unlink()
        self.assertIsNone(git_checkout_root(self.repo))
        other = self.root / "external.py"
        other.write_text("# Not the running checkout's module.\n")
        module.symlink_to(other)
        self.assertIsNone(git_checkout_root(self.repo))


class ReleaseIdentity(Fixture):
    def test_single_screen_and_temporarily_incomplete_screen_listing(self):
        complete = SimpleNamespace(stdout="123.lane-only (Detached)\n1 Socket in /tmp/screens.\n", stderr="")
        partial = SimpleNamespace(stdout="123.lane-only (Unreachable)\n1 Socket in /tmp/screens.\n", stderr="")
        with patch("live_status_snapshot.subprocess.run", side_effect=[partial, complete]):
            self.assertEqual(_screen_sessions(self.root), {"lane-only": "123.lane-only"})
        with patch("live_status_snapshot.subprocess.run", return_value=partial):
            self.assertIsNone(_screen_sessions(self.root))

    def test_assets_and_header_come_from_code_not_persistent_data(self):
        stale = self.folder / "static"
        stale.mkdir()
        for name in ("app.js", "style.css", "index.html", "login.html"):
            (stale / name).write_text("OLD UI")
        server = Server(("127.0.0.1", 0), self.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = Client(f"http://127.0.0.1:{server.server_port}", self.folder / ".password")
        try:
            with patch("app.HERE", self.folder):
                self.assertEqual(client.call("/api/version"), BUILD)
                client.login()
                with client.opener.open(client.url + "/") as response:
                    index = response.read().decode()
                    self.assertIn("no-cache", response.headers["Cache-Control"])
                    self.assertIn("no-store", response.headers["Cache-Control"])
                for name in ("app.js", "style.css", "manifest.webmanifest"):
                    url = "/" + name + "?v=" + BUILD["short_sha"]
                    self.assertIn(url, index)
                    with client.opener.open(client.url + url) as response:
                        self.assertEqual(response.read(), (STATIC / name).read_bytes())
                self.assertIn('id="build-info"', index)
                self.assertIn(BUILD["built_at"], index)
                self.assertNotIn("__WEBBOB_", index)
                self.assertNotIn("OLD UI", index)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_version_reply_is_only_own_sha_despite_other_project_history_and_hold(self):
        (self.root / "BOB-STATE.md").write_text("WebJam build deadbee. Web Bob is old1234.")
        self.chat.submit(self.identifier, "hold off", str(uuid.uuid4()))
        for prompt in ("what version/build are you", "What build are you running?", "What is your build number?",
                       "What version are you?", "What SHA are you running?"):
            reply = self.chat.submit(self.identifier, prompt, str(uuid.uuid4()))
            self.assertEqual(reply["messages"][-1]["content"], BUILD["short_sha"])
        self.assertFalse(self.fake.calls)
        self.assertFalse(VERSION_QUESTION.search("What version is WebJam?"))

    def test_archive_identity_uses_release_manifest_and_never_parent_git(self):
        self.assertEqual(load_build(self.root)["sha"], "unknown")
        manifest = dict(sha="a" * 40, built_at="2026-09-27T22:00:00+00:00")
        (self.root / "webbob-build.json").write_text(json.dumps(manifest))
        self.assertEqual(load_build(self.root)["short_sha"], "a" * 7)
        self.assertEqual(load_build(self.root)["built_at"], manifest["built_at"])

```

### FILE: webchat/test_integrate_2057.py
```python
"""Every original Jeff turn, plus forged effects and failed dispatches."""
import copy
import json
import subprocess
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat
from dispatch_receipts import NO_DISPATCH, receipt_errors
from reply_authority import enforce
from task_dispatch import task_queue as queue
from test_webbob_replyq_1856 import SessionFixture

SESSIONS = json.loads(Path(__file__).with_name("fixtures").joinpath("integrate_sessions_0927.json").read_text())["sessions"]


class PinnedDeploymentAssignments(SessionFixture):
    def setUp(self):
        super().setUp()
        from build_info import CODE_ROOT
        self.code_root = Path(__file__).resolve().parents[1]
        self.assertEqual(CODE_ROOT, self.code_root)
        self.assertEqual(Path(subprocess.check_output(
            ["git", "-C", str(self.code_root), "rev-parse", "--show-toplevel"], text=True).strip()).resolve(),
            self.code_root)
        self.pins = self.root / "conductor/state"
        self.pins.mkdir(parents=True, exist_ok=True)
        for name in ("webchat", "dispatch"):
            (self.pins / (name + "-code-root")).write_text(str(self.code_root) + "\n")
        # Attempt 0204 had this screen only: no identifiable project lane.
        sampler = patch("live_status_snapshot._screen_sessions", return_value={
            "lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"})
        sampler.start()
        self.addCleanup(sampler.stop)

    def test_attempt2_turn_one_dispatches_from_the_matching_release_pins(self):
        from integration_rubric import check_reply, sessions
        from live_status_snapshot import build_live_status_snapshot
        exchange = sessions()[0]["exchanges"][0]
        before = build_live_status_snapshot(self.root)
        self.assertEqual(before["queue_counts"]["queued"], 0)
        self.assertEqual(before["queue_counts"]["claimed"], 0)
        self.assertEqual(before["work_counts"]["running"], 0)
        self.assertEqual(len(before["work"]), 1)
        lane = before["work"][0]
        self.assertEqual(lane["screen"], "lane-integrate-deploy-0204")
        self.assertEqual(lane["state"], "unverified")
        self.assertEqual(lane["source"], "screen")
        for field in ("project", "repo", "task", "job_id", "worker"):
            self.assertIsNone(lane.get(field), field)
        started = time.time()
        answer = self.send(exchange["message"])
        records = queue.tasks(self.root)
        after = build_live_status_snapshot(self.root)
        self.assertEqual(check_reply(answer, exchange, self.identifier, started, before, after, records), [])
        self.assertEqual(len(records), 2)
        self.assertEqual(after["work_counts"]["running"], 0)
        for row in records.values():
            self.assertEqual(row["status"], "queued")
            self.assertIsNone(row["source_job_id"])
            self.assertIn("Project: Web Bob", row["prompt"])
            self.assertIn("matching deployment pins", row["prompt"])
            self.assertIn("no current task or worker execution is confirmed", row["prompt"])
            self.assertNotIn("Ongoing task:", row["prompt"])
        self.assertFalse(self.fake.calls)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        replay = self.chat.submit(self.identifier, exchange["message"], answer["request_id"])["messages"][-1]
        self.assertEqual(replay["task_ids"], answer["task_ids"])
        self.assertEqual(replay["content"], answer["content"])
        self.assertEqual(set(queue.tasks(self.root)), set(records))

    def test_pins_are_context_without_an_open_screen_or_a_claim_of_running_work(self):
        with patch("live_status_snapshot._screen_sessions", return_value={}):
            answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
            self.assertEqual(len(answer.get("task_ids", [])), 2)
            status = self.send("What are you working on?")
        self.assertIn("waiting to run", status["content"])
        self.assertNotIn("running for", status["content"])

    def test_missing_empty_relative_mismatched_and_unreadable_pins_fail_closed(self):
        for name in ("webchat", "dispatch"):
            pin = self.pins / (name + "-code-root")
            for value in (None, "", ".", str(self.root), str(self.root / "missing")):
                with self.subTest(pin=name, value=value):
                    pin.unlink(missing_ok=True)
                    if value is not None:
                        pin.write_text(value)
                    answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
                    self.assertFalse(answer.get("task_ids"))
                    self.assertFalse(queue.tasks(self.root))
                    pin.write_text(str(self.code_root))
            pin.unlink()
            pin.mkdir()
            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
            pin.rmdir()
            pin.write_text(str(self.code_root))

    def test_pinned_context_respects_project_global_and_partial_release_holds(self):
        for hold, release, permitted in (
            ("Hold off on Web Bob", None, False),
            ("Hold off", None, False),
            ("Hold off", "Resume WebJam", False),
            ("Hold off", "Resume Web Bob", True),
            ("Hold off on WebJam", None, True),
        ):
            with self.subTest(hold=hold, release=release):
                self.identifier = self.chat.new_conversation()["id"]
                self.send(hold)
                if release:
                    self.send(release)
                before = set(queue.tasks(self.root))
                answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
                added = set(queue.tasks(self.root)) - before
                self.assertEqual(len(added), 2 if permitted else 0)
                if permitted:
                    for key in added:
                        self.assertTrue(queue.tasks(self.root)[key]["prompt"].startswith("Project: Web Bob\n"))
                else:
                    self.assertIn("current holds", answer["content"])

    def test_pins_do_not_authorize_other_projects_or_tool_workers(self):
        for text in ("Use Gemini and MiniMax for ongoing WebJam jobs",
                     "Use Codex for ongoing jobs", "Use all LLMs for ongoing jobs"):
            with self.subTest(text=text):
                self.assertIn("couldn't assign", self.send(text)["content"])
                self.assertFalse(queue.tasks(self.root))

    def test_parked_project_holds_survive_the_permitted_webbob_dispatch(self):
        conversation = self.chat.conversations[self.identifier]
        holds = {name: dict(request_id="parked", reason="Keep parked", released_projects=[])
                 for name in ("Barker", "Wildflower")}
        conversation["intent_state"]["holds"] = copy.deepcopy(holds)
        self.chat.save(conversation)
        answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
        self.assertEqual(len(answer.get("task_ids", [])), 2)
        self.assertEqual(self.chat.get(self.identifier)["intent_state"]["holds"], holds)
        for row in queue.tasks(self.root).values():
            self.assertTrue(row["prompt"].startswith("Project: Web Bob\n"))
            self.assertIsNone(row["publish_project"])

    def test_rollback_copy_without_git_evidence_cannot_supply_report_context(self):
        rollback = self.root / "rollback-copy"
        rollback.mkdir()
        for name in ("webchat", "dispatch"):
            (self.pins / (name + "-code-root")).write_text(str(rollback))
        with patch("worker_assignment.CODE_ROOT", rollback):
            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
        self.assertFalse(queue.tasks(self.root))

    def test_git_marker_without_a_repository_cannot_authorize_jobs(self):
        for marker in ("file", "directory"):
            with self.subTest(marker=marker):
                code = self.root / marker
                code.mkdir()
                (code / "webchat").mkdir()
                (code / "webchat/build_info.py").write_text("# Untracked identity fixture.\n")
                if marker == "file":
                    (code / ".git").write_text("not a git checkout\n")
                else:
                    (code / ".git").mkdir()
                for name in ("webchat", "dispatch"):
                    (self.pins / (name + "-code-root")).write_text(str(code) + "\n")
                with patch("worker_assignment.CODE_ROOT", code):
                    answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
                self.assertFalse(answer.get("task_ids"))
                self.assertFalse(queue.tasks(self.root))

    def test_nested_tracked_code_uses_its_git_root_with_pins_to_the_running_code(self):
        repo = self.root / "monorepo"
        code = repo / "apps/webbob"
        module = code / "webchat/build_info.py"
        module.parent.mkdir(parents=True)
        module.write_text("# Tracked identity module for the nested fixture.\n")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.STDOUT)
        git("init", "-b", "main")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Nested fixture")
        for name in ("webchat", "dispatch"):
            (self.pins / (name + "-code-root")).write_text(str(code) + "\n")
        with patch("worker_assignment.CODE_ROOT", code):
            answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
        records = queue.tasks(self.root)
        self.assertEqual([records[key]["requested_worker"] for key in answer.get("task_ids", [])],
                         ["gemini", "minimax"])
        self.assertTrue(all("matching deployment pins" in row["prompt"] for row in records.values()))

    def test_absolute_symlink_pins_resolve_to_the_running_checkout(self):
        alias = self.root / "release-link"
        alias.symlink_to(self.code_root, target_is_directory=True)
        for name in ("webchat", "dispatch"):
            (self.pins / (name + "-code-root")).write_text(str(alias) + "\n")
        self.assertEqual(len(self.send(SESSIONS[0]["exchanges"][0]["message"]).get("task_ids", [])), 2)

    def test_pinned_context_does_not_displace_a_permitted_ongoing_job(self):
        source = queue.enqueue(self.root, "external", "source", "Improve WebJam recording", kind="coding")
        answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
        rows = queue.tasks(self.root)
        self.assertEqual([rows[key]["source_job_id"] for key in answer["task_ids"]], [source["id"], source["id"]])

    def test_pinned_context_still_respects_maintenance_and_provider_unavailability(self):
        maintenance = self.root / "conductor/MAINTENANCE"
        maintenance.touch()
        self.assertIn("maintenance", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
        maintenance.unlink()
        for state in ("needs_key", "cooldown", "budget_exhausted"):
            with self.subTest(state=state):
                (self.root / "conductor/lanes.json").write_text(json.dumps({"minimax": {"state": state}}))
                self.assertIn(state.replace("_", " "), self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
                self.assertFalse(queue.tasks(self.root))


class IntegratedSessions(SessionFixture):
    def seed(self):
        return queue.enqueue(self.root, "external-project-work", str(uuid.uuid4()),
                             "Improve WebJam recording reliability", kind="coding", worker="codex", title="WebJam")

    def test_all_19_captured_messages_in_conversation_order(self):
        self.seed()
        checked = 0
        for source in SESSIONS:
            self.identifier = self.chat.new_conversation()["id"]
            for index, exchange in enumerate(source["exchanges"]):
                with self.subTest(session=source["source_id"], turn=index + 1, message=exchange["message"]):
                    before = set(queue.tasks(self.root))
                    started = time.time()
                    answer = self.send(exchange["message"])
                    records = queue.tasks(self.root)
                    identifiers = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
                    self.assertEqual(set(identifiers), set(records) - before)
                    self.assertEqual(receipt_errors(answer, records, self.identifier, answer["request_id"], started), [])
                    self.assertNotRegex(answer["content"], r"(?i)I'll make sure|actively adding work|ready|unknown task")
                    if source["source_id"].startswith("b33fac"):
                        if index in (0, 1, 5):
                            self.assertEqual([records[i]["requested_worker"] for i in identifiers], ["gemini", "minimax"])
                            self.assertEqual([records[i]["kind"] for i in identifiers], ["audit", "test-writing"])
                            for identifier in identifiers:
                                self.assertIn(records[identifier]["title"], answer["content"])
                        elif index == 6:
                            self.assertEqual(len(identifiers), 1)
                            self.assertEqual(records[identifiers[0]]["kind"], "coding")
                        elif index == 7:
                            self.assertEqual(answer["content"], "Hi Jeff!")
                            self.assertFalse(identifiers)
                        else:
                            self.assertEqual(answer["provider"], "state")
                            self.assertFalse(identifiers)
                            for name in ("Codex", "Claude", "Cursor", "Gemini", "MiniMax"):
                                self.assertIn(name, ans
<<truncated for prompt size>>

```

### FILE: services/test_api_workers.py
```python
"""Offline API job execution through the real scheduler, transport and ledger."""
import hashlib
import copy
import json
import os
import sys
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import api
import api_worker
import budget
import dispatch_worker
import lanes
import state
import worker
import workspaces
import web_dispatch
from api_tasks import MODELS
import test_dispatch as dispatch_fixture
from web_dispatch import task_queue as queue


class APIWorkerTests(unittest.TestCase):
    setUp = dispatch_fixture.DispatchTests.setUp
    tearDown = dispatch_fixture.DispatchTests.tearDown

    def repo(self):
        repo = self.root / "repo"
        repo.mkdir(exist_ok=True)
        workspaces.git(repo, "init", "-b", "main")
        (repo / "queue.py").write_text("def enqueue(job):\n    return job\n")
        (repo / "keys.env").write_text("GEMINI_API_KEY=fixture-must-not-be-sent\n")
        (repo / "webchat").mkdir(exist_ok=True)
        (repo / "webchat/.password").write_text("fixture-password-never-read")
        (repo / "linked.py").symlink_to(repo / "webchat/.password")
        workspaces.git(repo, "add", "queue.py", "keys.env", "webchat/.password", "linked.py")
        workspaces.git(repo, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Fixture")
        return repo

    def test_frozen_turn_one_reaches_both_api_transports_and_delivers_reports(self):
        self.frozen_turn_reports(deployed_checkout=False)

    def test_attempt2_without_a_project_lane_reaches_both_api_transports(self):
        self.frozen_turn_reports(deployed_checkout=True)

    def frozen_turn_reports(self, *, deployed_checkout):
        # Real chat -> queue -> scheduler -> worker -> metered API transport.
        # Only HTTP responses, lane health and semantic acceptance are fixtures.
        with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1] / "webchat"), *sys.path]):
            from app import Chat
            from build_info import CODE_ROOT
            from deploy_integrate import submit
            from dispatch_receipts import receipt_errors
            from integration_rubric import sessions
            from live_status_snapshot import observe_work

            if deployed_checkout:
                # Match restart()'s real pin layout. No project mapping or
                # report_repository mock: workers must inspect the pinned code.
                repo = Path(__file__).resolve().parents[1]
                self.assertEqual(CODE_ROOT, repo)
                self.assertEqual(Path(workspaces.git(repo, "rev-parse", "--show-toplevel")).resolve(), repo)
                self.assertEqual(workspaces.git(repo, "ls-files", "--error-unmatch", "webchat/build_info.py"),
                                 "webchat/build_info.py")
                (self.core / "state").mkdir()
                for name in ("webchat", "dispatch"):
                    (self.core / "state" / (name + "-code-root")).write_text(str(repo) + "\n")
                screens = {"lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"}
                evidence_file = "webchat/worker_assignment.py"
                context = "no current task or worker execution is confirmed"
            else:
                repo = self.repo()
                (self.core / "services").mkdir()
                (self.core / "services/projects.json").write_text(json.dumps({"Web Bob": {"repo": str(repo)}}))
                screens = {"lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
                evidence_file = "queue.py"
                context = "worker activity is unverified"
            (self.core / "keys.env").write_text("GEMINI_API_KEY=gemini-fixture-key\nMINIMAX_API_KEY=minimax-fixture-key\n")
            providers = Mock(spec=["reply"])
            providers.reply.side_effect = AssertionError("Assignments must bypass conversational models")
            chat = Chat(self.core / "webchat", self.root, providers)
            self.addCleanup(chat.close)
            cid = chat.conversation_list()["conversations"][0]["id"]
            parked_holds = {name: dict(request_id="parked", reason="Keep parked", released_projects=[])
                            for name in ("Barker", "Wildflower")}
            chat.conversations[cid]["intent_state"]["holds"] = copy.deepcopy(parked_holds)
            chat.save(chat.conversations[cid])
            started = time.time()
            # Use the deployment replay's submission function with an in-process
            # HTTP adapter; all chat/intent/journal code stays real and isolated.
            def call(route, payload=None):
                if route == "/api/messages":
                    return chat.submit(payload["conversation_id"], payload["message"], payload["request_id"])
                return chat.get(cid)
            with patch("live_status_snapshot._screen_sessions", return_value=screens), \
                    patch("live_status_snapshot.process_table", return_value={}):
                if deployed_checkout:
                    before = observe_work(self.root)
                    self.assertFalse(before["records"])
                    self.assertEqual(len(before["work"]), 1)
                    lane = before["work"][0]
                    self.assertEqual(lane["screen"], "lane-integrate-deploy-0204")
                    self.assertEqual(lane["state"], "unverified")
                    self.assertEqual(lane["source"], "screen")
                    for field in ("project", "repo", "task", "job_id", "worker"):
                        self.assertIsNone(lane.get(field), field)
                receipt = submit(SimpleNamespace(call=call), cid, sessions()[0]["exchanges"][0]["message"])
            rows = queue.tasks(self.root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(receipt_errors(receipt, rows, cid, receipt["request_id"], started), [])
            self.assertEqual([rows[key]["requested_worker"] for key in receipt["task_ids"]], ["gemini", "minimax"])
            self.assertEqual([rows[key]["kind"] for key in receipt["task_ids"]], ["audit", "test-writing"])
            providers.reply.assert_not_called()

            called = []
            def transport(argv, **kwargs):
                config = Path(argv[argv.index("--config") + 1]).read_text()
                payload = json.loads(Path(argv[argv.index("--data-binary") + 1][1:]).read_text())
                lane = "gemini" if "generativelanguage" in config else "minimax"
                current = next(row for row in queue.tasks(self.root).values() if row["status"] == "running")
                self.assertEqual(current["worker"], lane)
                self.assertEqual(current["model"], MODELS[lane])
                self.assertIsNone(current["source_job_id"])
                self.assertIn("FILE " + evidence_file, json.dumps(payload))
                self.assertIn(context, json.dumps(payload))
                if deployed_checkout:
                    self.assertIn("FILE webchat/build_info.py", json.dumps(payload))
                if not deployed_checkout:
                    self.assertNotIn("fixture-must-not-be-sent", json.dumps(payload))
                answer = lane + ": " + evidence_file + " needs a duplicate-enqueue regression. Tests were not run."
                if lane == "gemini":
                    self.assertIn("gemini-2.5-pro:generateContent", config)
                    result = dict(candidates=[dict(finishReason="STOP", content=dict(parts=[dict(text=answer)]))],
                                  usageMetadata=dict(promptTokenCount=100, candidatesTokenCount=30))
                else:
                    self.assertIn("https://api.minimax.io/v1/text/chatcompletion_v2", config)
                    self.assertEqual(payload["model"], "MiniMax-M2.7")
                    result = dict(choices=[dict(finish_reason="stop", message=dict(content=answer))],
                                  usage=dict(prompt_tokens=100, completion_tokens=30), base_resp=dict(status_code=0))
                Path(argv[argv.index("-o") + 1]).write_text(json.dumps(result))
                called.append(lane)
                return SimpleNamespace(returncode=0, stdout="200", stderr="")

            def launch(row):
                self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 0)

            with patch.object(lanes, "refresh", return_value={lane: dict(state="ready") for lane in MODELS}), \
                    patch.object(web_dispatch, "launch", side_effect=launch), \
                    patch.object(api, "CONDUCTOR", self.core), patch.object(api, "run", side_effect=transport), \
                    patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-fixture-key", "MINIMAX_API_KEY": "minimax-fixture-key"}), \
                    patch.object(dispatch_worker, "prepare_task") as prepare, \
                    patch.object(dispatch_worker.draft_publish, "publish") as publish:
                self.assertEqual(web_dispatch.tick(), 2)
            self.assertEqual(called, ["gemini", "minimax"])
            self.assertEqual(chat.get(cid)["intent_state"]["holds"], parked_holds)
            prepare.assert_not_called()
            publish.assert_not_called()
            for row in queue.tasks(self.root).values():
                self.assertEqual(row["status"], "succeeded")
                self.assertEqual(row["worker"], row["requested_worker"])
                self.assertGreaterEqual(row["execution_started_at"], started)
                self.assertEqual(Path(row["repo"]), repo)
                self.assertIn(row["result"], Path(row["result_path"]).read_text())
                self.assertEqual(row["result_sha256"], hashlib.sha256(row["result"].encode()).hexdigest())
                self.assertEqual(row["acceptance"]["result_sha256"], row["result_sha256"])
                self.assertTrue(row["evidence"]["files"])
                self.assertIsNone(row["branch"])
                self.assertIsNone(row["worktree"])
            chat.reconcile_tasks()
            chat.reconcile_tasks()
            messages = chat.history(cid)["messages"]
            saved = next(message for message in messages if message["id"] == receipt["id"])
            self.assertEqual(saved["content"], receipt["content"])
            self.assertEqual(saved["task_ids"], receipt["task_ids"])
            completed = [message for message in messages if message.get("task_status")]
            self.assertEqual(len(completed), 1)
            self.assertIn("Worker assignments completed: 2/2", completed[0]["content"])
            for identifier in receipt["task_ids"]:
                self.assertIn(identifier, completed[0]["content"])

    def test_both_workers_execute_real_claims_with_repo_evidence_and_reports(self):
        repo = self.repo()
        source = queue.enqueue(self.root, "conversation", "source", "Improve Web Bob", kind="coding")
        claim = queue.claim(self.root, "codex")
        queue.transition(self.root, source["id"], claim["claim_token"], "running", project="Web Bob", worktree=str(repo))
        for lane, task, kind in (("gemini", "Audit the whole repo", "audit"),
                                 ("minimax", "Write test cases for queue recovery", "test-writing")):
            with self.subTest(lane=lane):
                job = queue.enqueue(self.root, "conversation", lane, task, worker=lane, source_job_id=source["id"])
                self.assertEqual(job["kind"], kind)
                row = queue.claim(self.root, lane)
                def response(model, prompt, **kwargs):
                    self.assertEqual(model, lane)
                    self.assertEqual(kwargs["model_id"], MODELS[lane])
                    self.assertIn("FILE queue.py", prompt)
                    self.assertNotIn("fixture-must-not-be-sent", prompt)
                    self.assertNotIn("fixture-password-never-read", prompt)
                    self.assertNotIn("FILE linked.py", prompt)
                    current = queue.tasks(self.root)[job["id"]]
                    self.assertEqual(current["model"], MODELS[lane])
                    self.assertEqual(current["status"], "running")
                    return "queue.py: Add regression coverage for duplicate claims. Tests were not run.\n```diff\n+assert enqueue(job) == job\n```"
                with patch.object(api, "model_call", side_effect=response), \
                        patch.object(dispatch_worker, "prepare_task") as prepare, \
                        patch.object(dispatch_worker.draft_publish, "publish") as publish:
                    self.assertEqual(dispatch_worker.execute(job["id"], row["claim_token"]), 0)
                prepare.assert_not_called()
                publish.assert_not_called()
                result = queue.tasks(self.root)[job["id"]]
                self.assertEqual(result["status"], "succeeded")
                report = Path(result["result_path"])
                self.assertTrue(report.is_relative_to(self.core / "reviews"))
                self.assertIn("```diff", report.read_text())
                self.assertEqual((repo / "queue.py").read_text(), "def enqueue(job):\n    return job\n")
                self.assertIsNone(result["branch"])
                self.assertIsNone(result["worktree"])
                self.assertTrue(result["evidence"]["files"])

    def test_transport_loads_keys_uses_exact_models_and_search_without_secret_logs(self):
        (self.core / "keys.env").write_text("export GEMINI_API_KEY='gemini-fixture-key'\nMINIMAX_API_KEY=minimax-fixture-key\n")
        calls = []
        def transport(argv, **kwargs):
            config = Path(argv[argv.index("--config") + 1]).read_text()
            payload = json.loads(Path(argv[argv.index("--data-binary") + 1][1:]).read_text())
            self.assertNotIn("fixture-key", " ".join(argv))
            self.assertNotIn("?key=", config)
            if "generativelanguage
<<truncated for prompt size>>

```

### FILE: webchat/deploy_parity.py
```python
#!/usr/bin/env python3
"""Pinned draft deploy; snapshot first, restart two services, verify or roll back."""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True, check=True, timeout=60, **kwargs).stdout.strip()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    temporary.replace(path)


def restart(root, pins, expected_exits=()):
    # Use the same supervisor lock as watchdog; no competing automatic restart.
    from state import lock
    from runtime import screen_sessions, stop_service_process, service_lock_held
    with lock("supervisor"):
        before = screen_sessions()
        listener = subprocess.run(["lsof", "-t", "-iTCP:8787", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10)
        pids = set(listener.stdout.split())
        if len(pids) > 1 or listener.returncode not in (0, 1):
            raise RuntimeError("restart: cannot identify webchat listener")
        pid = int(next(iter(pids))) if pids else None
        if pid:
            command = run(["ps", "-p", pid, "-o", "command="])
            if str(root) not in command or "/webchat/app.py" not in command:
                raise RuntimeError("restart: listener ownership mismatch")
        for name, code in pins.items():
            write(root / "conductor/state" / (name + "-code-root"), str(code) + "\n")
        for name in ("svc-webchat", "svc-job-runner"):
            if name in before:
                run(["screen", "-S", before[name], "-X", "quit"])
        stop_service_process("job-runner")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _ in range(60):
            if not pid:
                break
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.25)
        else:
            raise RuntimeError("restart: old webchat did not exit")
        env = dict(os.environ, BOB_ROOT=str(root), BOB_WEBCHAT_DISPATCH="1", BOB_WEBCHAT_DRILLS="0")
        run(["screen", "-dmS", "svc-webchat", "/bin/bash", root / "conductor/webchat/run.sh"], env=env)
        run(["screen", "-dmS", "svc-job-runner", "/bin/bash", root / "conductor/services/job-runner.sh"], env=env)
        for _ in range(80):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8787/login", timeout=1) as response:
                    healthy = response.status == 200 and response.headers.get("X-Bob-Webchat") == "1"
                if healthy and service_lock_held("job-runner"):
                    break
            except OSError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError("restart: webchat or job-runner did not become healthy")
        after = screen_sessions()
    unrelated = {name: identity for name, identity in before.items()
                 if name not in ("svc-webchat", "svc-job-runner") and name not in expected_exits}
    return dict(before=before, after=after, restarted_services=["webchat", "job-runner"],
                permitted_replay_exits=list(expected_exits),
                other_screens_unchanged=all(after.get(name) == identity for name, identity in unrelated.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--draft-pr", required=True)
    args = parser.parse_args()
    root, candidate = args.root.resolve(), args.candidate.resolve()
    os.umask(0o077)
    os.environ["BOB_ROOT"] = str(root)
    sys.path.insert(0, str(candidate / "services"))
    from live_redeploy_check import Client, verify_four, follow_through, require
    from providers import Redactor
    from task_dispatch import task_queue
    reviews = root / "conductor/reviews"
    sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
    require(run(["git", "-C", candidate, "branch", "--show-current"]) == "draft/webbob-parity-1633", "Wrong candidate branch")
    require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate is not clean")
    run(["git", "-C", candidate, "merge-base", "--is-ancestor", "7c9ed94", sha])
    pr = json.loads(run(["gh", "pr", "view", args.draft_pr, "--json", "isDraft,headRefOid,baseRefName"]))
    require(pr["isDraft"] and pr["headRefOid"] == sha and pr["baseRefName"] == "draft/webbob-clean-0927", "Draft PR does not match candidate/base")
    client = Client("http://127.0.0.1:8787", root / "conductor/webchat/.password")
    client.login()
    session = client.call("/api/session")
    require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight; retry after it finishes")
    redact = Redactor(root, client.password_file.read_text().strip())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rollback = root / "rollbacks" / ("webbob-parity-" + stamp)
    rollback.mkdir(mode=0o700)
    previous, snapshots = {}, {}
    for name in ("webchat", "dispatch"):
        pin = root / "conductor/state" / (name + "-code-root")
        previous[name] = Path(pin.read_text().strip()).resolve() if pin.exists() else root / "conductor"
        copy = rollback / ("previous-" + name)
        shutil.copytree(previous[name], copy, ignore=shutil.ignore_patterns(
            ".git", ".password", ".session-secret", "keys.env", "sessions", "node_modules", "__pycache__", "uploads", "evidence", "task-runs"))
        snapshots[name] = copy
    evidence = dict(sha=sha, draft_pr=args.draft_pr, rollback=str(rollback), previous_pins={k:str(v) for k,v in previous.items()},
                    snapshots={k:str(v) for k,v in snapshots.items()}, all_pass=False)
    record = reviews / "WEBBOB-PARITY-DEPLOYMENT-0927.json"
    write(rollback / "release.json", json.dumps(evidence, indent=2) + "\n")
    def save():
        write(record, redact(json.dumps(evidence, indent=2)) + "\n")
    save()
    activated = False
    try:
        write(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        activated = True
        evidence["deployment"] = restart(root, dict(webchat=candidate, dispatch=candidate))
        save()
        print("Deployed " + sha[:7] + "; rollback " + str(rollback), flush=True)
        client = Client(client.url, client.password_file)
        checks_path = reviews / "WEBBOB-PARITY-LIVE-0927.json"
        checks = verify_four(client, root, checks_path)
        checks = follow_through(client, root, checks_path, checks, sha)
        evidence["live_checks"] = checks
        require(checks["all_pass"], checks.get("failure", "Live checks failed"))
        print("Review finished; both project drafts pushed and verified. Checking public Jobs UI.", flush=True)
        screenshot = reviews / "WEBBOB-PARITY-JOBS-0927.png"
        origin = (root / "conductor/webchat/.public-origin").read_text().strip()
        env = dict(os.environ, BOB_PLAYWRIGHT_MODULE=str(root / "conductor/webchat/node_modules/playwright"))
        browser = subprocess.run(["node", str(candidate / "webchat/capture_parity.cjs"), str(root), origin, sha,
                                  str(screenshot), str(reviews / "WEBBOB-PARITY-BROWSER-0927.json")],
                                 capture_output=True, text=True, timeout=120, env=env)
        require(browser.returncode == 0, "public Jobs/assets: " + browser.stderr[-1500:])
        for name in ("claude161", "push2"):
            for job in checks["checks"][name]["jobs"]:
                row = task_queue.tasks(root)[job["id"]]
                require(row["status"] != "failed", name + ": job failed during browser check: " + str(row.get("error")))
        evidence.update(all_pass=True, jobs_screenshot=str(screenshot), finished_at=time.time())
        save()
        write(root / "conductor/LOOP-TIME-TO-TEST-0927.txt",
              "PASS\nSHA: " + sha + "\nDraft PR: " + args.draft_pr + "\nJobs screenshot: " + str(screenshot) +
              "\nRollback: " + str(rollback) + "\nPR #161 actual reviewer: " + checks["checks"]["claude161"]["actual_worker"] +
              "\nTests: full webchat/services discovery + JavaScript; see reviews/WEBBOB-PARITY-TESTS-0927.txt\n" +
              "Live checks: status, PR review completion, two verified project draft pushes, hold off/go, own build SHA, public assets and Jobs.\n")
        print("PASS " + sha[:7] + " " + args.draft_pr + " " + str(screenshot), flush=True)
        return 0
    except Exception as exc:
        evidence["failure"] = redact(str(exc))
        if activated:
            try:
                evidence["rollback_result"] = restart(root, snapshots)
                evidence["rolled_back"] = True
            except Exception as rollback_error:
                evidence["rollback_error"] = redact(str(rollback_error))
        save()
        write(reviews / "WEBBOB-REDEPLOY-FAIL-0927-b.md", "# Web Bob parity redeploy — FAIL\n\n" +
              "Candidate: `" + sha + "`\n\nDraft PR: " + args.draft_pr + "\n\nExact failing check: " + evidence["failure"] +
              "\n\nRollback: `" + str(rollback) + "`. Restored: " + str(evidence.get("rolled_back", False)) +
              "\n\nEvidence: WEBBOB-PARITY-DEPLOYMENT-0927.json and WEBBOB-PARITY-LIVE-0927.json.\n")
        print("FAIL " + evidence["failure"] + "; rolled back=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

```

### FILE: webchat/README.md
```python
# Bob web chat

Open **http://127.0.0.1:8787** on the mini. The login password is in
`conductor/webchat/.password` (owner-only, mode 600). To see it locally:

```bash
cat ~/Documents/bob-overnight-inject/conductor/webchat/.password
```

The app uses Python's standard library. No packages, API account changes, or
Claude subscription are needed. The messenger supports mobile layouts, dark mode,
saved conversation selection, new conversations, polling replies, and Stop.
Enter sends on a desktop; Shift+Enter adds a line. On a phone, use Send.

The five tabs are Chat, Jobs, Songs, Models and Settings. Jobs shows current
workers and saved results; View jobs in Chat opens it without sending a message.
Models shows current activity and reply availability, with measured usage in
collapsed details. Songs puts lyrics and Save first, with chords, audio and saved
versions below. Settings saves your preferred first-choice model on this device.
Opening these tabs does not request a model answer or change the queue.

## Conversation and provider behavior

Short messages use a fast path (**Gemini → MiniMax → Cursor → Codex**, a 60s initial budget,
then any untried providers), per the later `WEBCHAT-READY.md` phone brief.
Longer/coding/debug work tries **Codex → Cursor → Gemini → MiniMax**. Claude is never in the
automatic route. Codex uses the existing ChatGPT login with API-key environment variables
removed and `forced_login_method="chatgpt"`. No credentials are changed. Native
`codex exec resume <exact-thread-id>` preserves continuity; it never uses `--last`
and therefore never picks up an unrelated coding job. Unsupported/unavailable
saved sessions use recent conversation context. See the official
[Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

Cursor uses `cursor-agent --trust --mode ask --print --output-format json`.
Gemini and MiniMax use `webchat/api_call.py`, which calls the same metered
`services/api.py`/`budget.py` transport as the ask scripts, sharing three bounded
API slots per provider. MiniMax has a **$59 chat ceiling** even if background credit
is increased elsewhere; the child process applies the lower of the chat and shared caps.
Reservations and uncertain calls count toward the cap. Lane health shows that
committed amount, not just settled charges.
Both API lanes default to a $48 shared ceiling, warn at 70%, reduce concurrency
to one at 85%, and reject reservations that would cross 95%. Configure lower
ceilings with `BOB_GEMINI_CAP_USD` and `BOB_MINIMAX_CAP_USD`. CLI plan percentages
are unknown unless observed quota data is supplied in the private
`conductor/plan-usage.json`, for example `{"codex":{"used_percent":86,"reset_at":1790535600}}`.
Observed 95% usage stops that CLI until its reset; provider rate-limit responses
also impose cooldowns. Token counts and estimated dollars do not stand in for
subscription quota measurements.

## Max-mode tasks

Ordinary work requests such as `Ok figure out what is wrong with Gemini` and
`fix the login button` go directly to the durable dispatcher. A server receipt names
the job only after the queue write succeeds; claim updates name the actual worker,
and the completed result is posted in the originating conversation. Model prose
cannot acknowledge queue or inbox effects. Explicit small text writes such as
`write hello to /tmp/example.txt` use Codex, Cursor or Claude with file
tools; success requires the server to verify the changed file and its contents.

Named multi-project requests create one durable job per project. For example,
`prioritize Web Bob, WebJam, AdoptIQ, StoryBoard` saves the order; `push everything
to the max and fix anything you find` queues four project jobs. Each receipt sentence
names the project and requested worker; job IDs stay in structured job data. Assignment prefers ready
compatible lanes and accounts for existing claims and queued work. Coding jobs
use Codex/Cursor; Gemini and MiniMax produce repository reports and proposed patches.

“Remember you can use Gemini and MiniMax for the ongoing jobs” now assigns real
jobs: Gemini gets a whole-repository audit and plan, and MiniMax gets a review
with regression test drafts. The server names each task, worker and durable job
ID after saving it. Existing coding claims continue unchanged. Missing work,
holds, maintenance or unavailable lanes get an honest explanation, never a
readiness-only acknowledgement. A queued receipt means waiting for runner
capacity; a started receipt requires a recorded worker claim.

When no permitted ongoing job or identified project lane remains, matching
webchat and dispatcher deployment pins can identify the running Web Bob Git
checkout for these API reports. The assignments explicitly say no current task
or execution is confirmed. This fallback only supplies Web Bob repository
context to API workers; project/global holds, maintenance and provider
availability still apply. Missing or mismatched pins cannot supply context.
`webchat/build_info.py` is a tracked source module: `CODE_ROOT` comes from its
resolved `__file__`, never a generated manifest or the persistent `BOB_ROOT`.
Git must resolve a real checkout and find that module in HEAD. Normal checkouts,
linked worktrees (`.git` files), and tracked nested code directories are supported;
an untracked rollback/archive under another repository cannot borrow its identity.
The pins at `conductor/state/webchat-code-root` and `dispatch-code-root` must
both contain absolute paths resolving to that running code directory (including
the code subdirectory in a nested layout). Deployment writes absolute paths with
a trailing newline; absolute symlink aliases are accepted, relative paths are
rejected because the services can start from different working directories.
An unverified `lane-integrate-deploy-0204` screen with no project, repository or
task does not supply project context or block this fallback. The attempt2
regressions assert those observed fields before checking real Gemini `audit`
and MiniMax `test-writing` jobs, while preserving Barker and Wildflower holds.

Named API requests also support audits, planning, research, repository reviews,
test-case writing and eval grading. Gemini job calls use `gemini-2.5-pro`;
research enables `google_search`. MiniMax uses `MiniMax-M2.7`. The runner supplies
bounded tracked repository evidence, omitting credentials, links and private
runtime files. Accepted reports and fenced proposed patches are saved under
`conductor/reviews/api-workers/`; API workers never deploy, apply changes or
resolve conflicts. Status and Jobs show the task and exact executing model.

Conversation files also save explicit holds and the latest permission transition.
`hold off on Web Bob` blocks new submissions for that project; `go`, `resume`, or
`the hold is lifted` clears the applicable hold. An explicit project push also
authorizes those projects. A held request survives a reload and can be resumed.
Holds govern new chat submissions; they do not stop already queued/running jobs
or restart services. Old conversations migrate user directives in order without
dispatching them, and assistant text cannot restore a cleared hold.

Status questions, including `is it moving along now?`, get a short server summary
of live work: task label, worker/model and elapsed process time. Read-only `screen
-ls` and `ps` observations include `lane-*` work and standalone CLI workers outside
the queue. Queue claims, screen descendants and CLI wrappers are joined to avoid
duplicates; live workers override cached ready lanes. Desktop apps and helpers
are excluded. Open screens without a confirmed worker and unavailable checks are
reported as unverified. A running process proves activity, not forward progress;
an exact model variant is shown only when present in the process arguments.
Task labels come from queue titles/projects or readable screen names, never raw
process prompts. Missing task details use a readable project or lane label; missing exact model metadata stays unreported. Internal job IDs, screen
names, PIDs and finished-job history are shown only when requested. Ordinary chat
never recommends special job syntax.

Operational replies also use lane locks and generation health from
`webchat/sessions/provider-health.json` plus `logs/webchat-failover.log`. The server
identifies the actual answering provider on each attempt. Old chat errors never
override recovered health, and configuration probes alone do not prove generation.

Say `Max mode: review ...` or `Go to the max: implement ...`. Web Bob saves a
restart-safe plan and queues independent packages for Codex (implementation),
Cursor (integration/tests), Claude (design critique), Gemini (alternatives and
capacity), MiniMax (failures/recovery), and mini (local tests). The default split
uses these standing roles; provide task-specific packages when boundaries matter:

```text
Max mode: review this design and supplied evidence ...
[codex] Inspect queue invariants and cite code.
[cursor] Inspect the delivery path and test coverage.
[claude] Critique assumptions using the supplied evidence.
[gemini] Calculate throughput under the stated durations.
[minimax] Analyze crash recovery using the supplied evidence.
[mini] Run services/test_services.py.
```

API report packages receive a server-collected repository snapshot. Claude and
answer-only analysis packages still need evidence in the request.
Coding packages own separate production/test files on private draft branches.
Local commits are reported for review; max mode does not integrate or publish
them. Mini accepts existing `services/test_*.py` or `webchat/test_*.py` suites,
uses an isolated data root, strips credential environment variables, and has a
five-minute execution limit.

The runner refills available slots every five seconds, routes analysis to Claude
and API workers before tool workers, and shifts failed or capped work to a
compatible provider with headroom. Busy pinned lanes retain their queued work.
After every package finishes or exhausts retries, a local reducer posts one
combined answer with attributed results and failures. It preserves disagreements
and does not spend another provider call to deliver the results. Saved answers
and deterministic group IDs prevent duplicate delivery across restarts.

Explicit chat provider choices try that provider first, then the normal fallback
chain. Claude remains explicit-only in ordinary chat and participates in max mode.
`/api/jobs` exposes group membership, attempts, PIDs and execution timestamps.
Run `python3 webchat/live_maxmode_proof.py run --root <live-data-root>` for the
authenticated five-provider overlap proof; `resume` and `verify` reuse its private
receipt without submitting another request.
Fallbacks receive up to the last 20 messages (24,000 characters) plus bounded, redacted handoff, brain,
status, review and queue snapshots. The provider and fallback reasons appear
beside the reply. An exhausted provider chain produces an honest queued message.
The saved turn automatically retries when a cooldown expires; Stop cancels it.

Codex runs read-only with no approval prompts or inherited user-config MCP tools;
Cursor runs in ask mode for chat. Providers answer from supplied context. The
separate server dispatch handler queues work; model replies cannot invoke it.
Every provider receives the current
handoff and the hard rules: drafts only, no merges/undrafts/force-push, no outward
messages without Jeff's yes to the exact text, no spending/login changes, no
touching Andrea or other workers' edits, and one WebJam coder. Older brain memory
cannot override those rules.

`sessions/<uuid>.json` stores each conversation and its Codex thread ID, mode 600
inside a mode-700 directory. Conversation history survives server restarts.
Login cookies expire after 12 hours and are invalidated by logout or a restart.
An interrupted running reply is marked as interrupted; it is never automatically
replayed. A waiting all-down request survives restart with its original user turn
and refreshed operational context.
Only one reply runs **per conversation** — not globally across all chats (other conversations can reply in parallel). CLI
calls use `chat-<provider>` locks separate from background `lane-*` locks; a busy
CLI slot falls through to the next provider. Handback: `conductor/handback/`
(BOB-STATE in, HANDBACK-LOG out). Natural requests such as `fix the login button`,
`review PR #161`, and `have Claude review this design` queue durable tasks without
a second confirmation. `go` accepts the most recent clear work proposal; an
ambiguous request gets one short question. Ordinary answers have no job footer.
Receipts say, for example, `I queued “Review PR #161” for Claude.` only after
the durable write. They remain unchanged at their original timestamps.
Structured job data records actual claims and execution; a separate completion
message names the actual worker and links verified project results.
The job runner launches work as capacity becomes available; nothing merges
automatically. Retransmitting the same request ID does
not duplicate work. The server saves intent before queue writes and acknowledges
the job only after the fsynced journal append. Interrupted writes are reconciled
idempotently. Queue updates share a lock and fence stale claim tokens.

Stop and per-provider deadlines terminate the process group and captured nested
groups belonging to this chat. Stdin is an EOF-terminated prompt file or
`/dev/null`. Defaults: Codex/Cursor 180s; Gemini/MiniMax/explicit Claude 120s.
Override a lane with `BOB_WEBCHAT_TIMEOUT_CODEX` (or `_CURSOR`, `_GEMINI`,
`_MINIMAX`, `_CLAUDE`), 15–600s. `BOB_WEBCHAT_TIMEOUT` supplies the CLI default.

Failures are classified as sign-in, usage limit, timeout, nonzero exit, invalid
output or network. Breakers cool for 5, 10, 20, then 30 minutes; a parseable usage
reset overrides that duration. One half-open attempt tests recovery. Suc
<<truncated for prompt size>>

```
