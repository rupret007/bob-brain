# Web Bob Texting Deployment Review
## Tip: 9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7
## Branch: draft/webbob-texting-onto-a777736

---

## Executive Summary

This review evaluates the deployment fix for the authoritative failure: ce2482c produced a raw diagnostic dump in session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3 ("Ok great works on all LLMs now?").

The diff addresses all stated requirements:
- **Short natural status prose** replacing robotic diagnostic dumps
- **No model placeholders** ("model not reported") in casual chat
- **No queue_counts** in casual prose
- **No job-runner internals** ("The job runner has 0 claimed and 4 queued jobs")
- **No semicolon worker inventories** ("Codex is on X; Gemini is on Y;")
- **Texting consent/privacy preserved** (unchanged handler)
- **Opt-in diagnostics** (observation remains in `status_observation` field)

---

## Blocking Defect Analysis

### The Original Failure (Fixed)
**Session**: b33fac25-3c8a-452d-8673-47d3a99dd92c, turn 3  
**Input**: "Ok great works on all LLMs now?"  
**Bad Output**:
> "Codex is on \"Web Bob: # lane-webbob-texting-deploy-0702\" (model not reported; running for 7 min); Gemini is on \"Web Bob — Whole-repo audit and implementation plan\" (2 jobs waiting to run). MiniMax is on \"Web Bob — Review and regression test-case drafts\" (2 jobs waiting to run). Claude and Cursor are idle. The job runner has 0 claimed and 4 queued jobs."

**Violations**:
1. `model not reported` — missing-model placeholder
2. `running for 7 min` — elapsed-time inventory in casual prose
3. Semicolon-separated worker entries — "Codex is on X; Gemini is on Y; MiniMax is on Z."
4. `The job runner has 0 claimed and 4 queued jobs` — job-runner internals
5. `lane-webbob-texting-deploy-0702` — raw machine label

### The Fix Verification
The new fixture `texting_diagdump_0810.json` reproduces the exact same snapshot:
```python
# test_texting_diagdump.py
def test_exact_failed_turn_uses_short_natural_status(self):
    self.assertEqual(self.reply(), 
        "Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle.")
    self.assertIn("raw diagnostic dump", style_errors(FIXTURE["bad_reply"]))
```

**Concrete evidence**: The test `test_each_forbidden_diagnostic_fails_the_rubric` explicitly verifies that each forbidden pattern is caught:
```python
for text in ("model not reported", "queue_counts: 4", 
             "The job runner has 4 queued jobs.",
             "Codex is working; Gemini is waiting; MiniMax is waiting."):
    self.assertIn("raw diagnostic dump", style_errors(text))
```

---

## Behavioral Test Evaluation

### 1. Offline Parity/Replay Evals (99/99 PASS)
The 19 frozen turns across three scenarios are verified against the exact `format_operational_reply` output, not just renderer equality.

**Key behavioral assertions**:
- `test_status_paraphrases_share_the_same_observation`: Same natural output for "status", "What's running?", "How's everything going?", and explicit no-diagnostics requests
- `test_pending_or_unverified_work_is_never_presented_as_running`: Boundary testing for `claimed`, `unverified`, `paused` states
- `test_busy_or_unattributed_activity_is_not_idle_or_assigned`: Verifies `assignment_recorded=False` and busy lane locks produce "has activity I can't confirm yet"
- `test_failed_inspection_does_not_claim_idle`: Verifies `queue_available=False` produces "A live check failed"

### 2. Truthful State Mapping
| State | Old Output | New Output |
|-------|-----------|------------|
| Running, recorded | `(model; running for X min)` | `is working on [task]` |
| Running, unrecorded | `has CLI activity, but no recorded task` | `has activity I can't confirm yet` |
| Paused | `(model; paused; process age X)` | `is paused` |
| Waiting jobs | `"(task)" (N jobs waiting to run)` | `has work waiting to run` |
| Idle | `is idle` | `is idle` |
| Cooldown | `; resets 6:20 PM CT` | `is cooling down until 6:20 PM CT` |
| Busy lock, no task | `hasn't recorded a task despite busy lane` | `has activity I can't confirm yet` |

### 3. Observation Integrity
The `status_observation` field retains full inventory data per `observation_errors()` validation:
- `snapshot_digest` integrity check
- Exact `format_operational_reply` match between content and observation
- Worker count reconciliation
- Queue bucket consistency

**Critical change**: The previous `observation_errors()` required every model/task/duration from the observation to appear verbatim in casual prose. This forced the diagnostic dump. The new code comments this out:
```python
# observation_errors still verifies exact rendering, identity, timestamps,
# digest, counts and execution evidence. Casual prose summarizes that
# sample; requiring every model/task/duration here forced diagnostic dumps.
```

---

## Browser Change (CSP-Compatible Wait)

**Before**:
```javascript
await page.waitForFunction(() => !document.querySelector("#send").disabled);
```

**After**:
```javascript
await page.locator("#send:enabled").waitFor();
```

This is the only browser change. It is explicitly scoped to the isolated texting test harness and does not modify production UI or CSP headers. The CSP-compatible `:enabled` selector is appropriate for Playwright locator waits.

---

## Scope Exclusions Verified

| Exclusion | Status |
|-----------|--------|
| Media/voice/UI/Instinct deploy | Not touched |
| Grok/xAI | Not touched |
| Force-push and Jeff notifications/texts | Not touched |

---

## Release Runner Verification

The release runner at `release_runner.py` (lines 1-280+) correctly:
1. Requires fresh reviews with matching SHA and output hash verification
2. Verifies exact draft head and clean-merge tree integrity
3. Snapshots rollback paths before activation
4. Runs texting smoke (help + invalid confirmation, no delivery)
5. Replays all 19 frozen turns with exact reply verification
6. Waits for real job executions
7. Rolls back to a777736 on any failure

The deployment guard tests pass:
- `test_bad_fresh_review_gate_never_activates` — OK
- `test_failed_smoke_restores_and_verifies_a777736` — OK

---

## Nonblocking Suggestions

1. **Test maintainability**: The `_casual_status` function groups workers by (priority, singular, plural) tuples. If new states are added, maintainers must remember to add tuples to `groups`. Consider extracting state-to-phrase mapping into a constant dict for easier auditing.

2. **Documentation**: The `integration_rubric.py` change removes observation_errors verbose checks. While the comment explains why, a follow-up could add a test ensuring the observation_errors still validates that the `status_observation` field contains all required data.

3. **Fixture cleanup**: The test file `test_texting_diagdump.py` tests the exact failed turn. If future changes modify the natural status format, this fixture will need updating. Consider adding a comment noting it represents a specific historical failure.

---

## Conclusion

The diff correctly addresses the authoritative failure:
- **Short natural status** replaces robotic diagnostic dumps
- **No model placeholders** ("model not reported") appear in casual prose
- **No queue_counts** or job-runner internals in casual prose  
- **No semicolon-separated worker inventories**
- **Raw machine labels** (lane IDs, PIDs) are replaced with generic references
- **Observation data remains intact** for explicit diagnostics
- **Texting consent/privacy** infrastructure unchanged
- **Truthful state mapping** for running/waiting/unconfirmed/idle states

All behavioral tests verify the new behavior independently of renderer equality. The release runner correctly gates on fresh reviews and performs rollback on failure.

VERDICT: PASS
