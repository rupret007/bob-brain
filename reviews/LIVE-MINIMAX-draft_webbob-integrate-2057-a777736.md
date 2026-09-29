Looking at the source bundle for tip `a777736` on `draft/webbob-integrate-2057`, I need to verify the scope items before the LIVE re-run.

## Verification

### 1. API workers live-dispatch under parked holds

**build_info.py:17-24** — `git_checkout_root()` filters inherited Git overrides:
```python
env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
```

**build_info.py:29-43** — Resolves Git root only when identity module is committed blob:
```python
if _git(code_root, "cat-file", "-t", "HEAD:" + relative) != "blob":
    return None
```

**worker_assignment.py:65-80** — `deployed_project_context()` requires matching pins and committed identity:
```python
if not path.is_absolute() or path.resolve(strict=True) != CODE_ROOT:
    return None
if git_checkout_root(CODE_ROOT) is None:
    return None
```

**test_integrate_2057.py:53-62** — attempt2 fixture explicitly verifies no project/worker/task:
```python
for field in ("project", "repo", "task", "job_id", "worker"):
    self.assertIsNone(lane.get(field), field)
```

**test_integrate_2057.py:104-110** — Parked holds survive permitted dispatch:
```python
conversation["intent_state"]["holds"] = copy.deepcopy(holds)
self.chat.save(conversation)
answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
self.assertEqual(len(answer.get("task_ids", [])), 2)
self.assertEqual(self.chat.get(self.identifier)["intent_state"]["holds"], holds)
```

**integration_rubric.py:118-131** — Rubric applies parked holds and verifies they persist:
```python
if deployed_checkout:
    if chat.get(cid)["intent_state"]["holds"] != parked_holds:
        errors.append("parked Barker/Wildflower holds changed")
```

### 2. Production checkout identity

**build_info.py:11** — `CODE_ROOT` from resolved `__file__`, not manifest:
```python
CODE_ROOT = Path(__file__).resolve().parents[1]
```

**test_build_info.py:49-57** — Detects linked worktrees (`.git` files):
```python
self.assertTrue((linked / ".git").is_file())
self.assertEqual(git_checkout_root(linked), linked)
```

**test_build_info.py:59-67** — Nested code requires commit in that nested location:
```python
self.git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Nested code")
self.assertEqual(git_checkout_root(nested), self.repo)
```

**test_integrate_2057.py:122-132** — Invalid marker rejection:
```python
(code / ".git").write_text("not a git checkout\n")
...
self.assertFalse(answer.get("task_ids"))
self.assertFalse(queue.tasks(self.root))
```

### 3. Rubric deployed_checkout / screen fixture vs fallback

**integration_rubric.py:102-109** — Attempt2 screen fixture:
```python
screens = {"lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"} if deployed_checkout else ...
```

**test_integrate_2057.py:54-62** — Explicitly verifies only unidentified deploy screen:
```python
if (len(lanes) != 1 or lanes[0].get("screen") != "lane-integrate-deploy-0204"
        or lanes[0].get("state") != "unverified" or lanes[0].get("source") != "screen"
        or any(lanes[0].get(key) for key in ("project", "repo", "task", "job_id", "worker"))):
    errors.append("attempt2 fixture must have only an unidentified deploy screen")
```

**test_integrate_2057.py:73-80** — Turn 1 still creates API jobs under holds:
```python
for row in records.values():
    self.assertEqual(row["status"], "queued")
    self.assertIsNone(row["source_job_id"])
    self.assertIn("Project: Web Bob", row["prompt"])
```

### 4. Session-freeze honesty

**worker_assignment.py:73-79** — Prompt explicitly says no confirmed execution:
```python
prompt=("The Web Bob checkout is selected by matching deployment pins for this server and its dispatcher; "
        "no current task or worker execution is confirmed. Inspect the supplied repository snapshot for ...")
```

**worker_assignment.py:43-48** — Never creates source_job_id for report jobs:
```python
if row.get("source_job_id") or (row.get("kind") in ("audit", "test-writing", ...)):
    continue
```

### 5. No force-push; draft-only; do not deploy

**deploy_parity.py:59-61** — Requires clean candidate:
```python
require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate is not clean")
```

**deploy_parity.py:72-74** — Creates rollback before any activation:
```python
rollback.mkdir(mode=0o700)
...
shutil.copytree(previous[name], copy, ...)
```

**deploy_parity.py:77-79** — Only activates after snapshot:
```python
write(candidate / "webbob-build.json", ...)
activated = True
evidence["deployment"] = restart(root, dict(webchat=candidate, dispatch=candidate))
```

### Resolution of Prior Gemini CRITICAL Claims (199eb19)

| Prior Finding | Evidence in a777736 |
|---|---|
| CRITICAL 1: unverifiable `build_info` dependency | **Resolved.** `build_info.py` blob tracked at `199eb19` (ec875bbde21864ae093bff8ea9dab7550e1e12ad). `git_checkout_root()` requires module as committed HEAD blob. Tests verify tracking. |
| CRITICAL 2: deploy screen contradicts fallback | **Resolved.** attempt2 fixture now explicitly verifies screen has no project/repo/task/worker/job_id. Rubric checks both screen fields and no source jobs. |

VERDICT: PASS
