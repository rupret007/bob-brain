Looking at `worker_assignment.py` diff, focusing on turn-1 Gemini/MiniMax API dispatch fallback when no permitted active source exists.

**Analysis of Fallback Logic (lines 91-107)**

```python
if not candidates and all(worker in task_queue.API_WORKERS for worker in workers):
```

This correctly gates the fallback to API workers only. The conditions checked:
- `row["state"] != "unverified"` — excludes running/claimed states
- `row.get("source") != "screen"` — requires screen source
- `row.get("job_id")` missing — ensures no existing job claim
- Screen exists in observed sessions
- Project, repo, and title all required

**Safety Guards Verified:**

1. **No fake job creation**: `id=None` for all fallback candidates; `source_job_id` set to `None`
2. **No coding jobs from fallback**: Prompts explicitly state "Its worker activity is unverified; no current task is confirmed"
3. **No invented source job ID**: Explicitly avoided per comment and code
4. **Recursive job protection**: Both candidate loops skip `kind in ("audit", "test-writing", ...)` rows
5. **Project holds respected**: `blocked_scopes(state, [project])` applied to fallback
6. **Target scope filtering**: Applied in both candidate loops and fallback

**Code Quality Observations:**

- `index % len(candidates)` safely distributes workers when candidates ≥ workers
- Empty candidates case raises `ValueError` before reaching modulo
- `seen_projects` prevents duplicate project candidates in fallback
- Grok/xAI rejected by `task_queue.worker_name()` before any queue operation

**No CRITICAL bugs found.**
**No HIGH bugs found.**

---

VERDICT: PASS
