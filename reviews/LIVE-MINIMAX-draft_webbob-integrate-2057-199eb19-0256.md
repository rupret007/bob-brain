Looking at the tip `199eb193396802bbbf899292e48cd04a55f9c57e` on branch `draft/webbob-integrate-2057`, I need to audit the production checkout fallback for API workers dispatch under holds.

## Analysis of the Patch

### Critical Review Points

**1. `deployed_project_context()` function (worker_assignment.py lines 62-80):**
- ✅ Verifies CODE_ROOT has `.git` directory
- ✅ Reads both webchat and dispatch pins from `conductor/state/`
- ✅ Validates both are absolute paths
- ✅ Uses `resolve(strict=True)` to canonicalize paths
- ✅ Returns context only when both pins match the running CODE_ROOT
- ✅ Prompt explicitly states "no current task or worker execution is confirmed"
- ✅ Does not fabricate source_job_id or running work claims

**2. Integration in `plan()` function (worker_assignment.py lines 142-146):**
```python
if not candidates and (not targets or "Web Bob" in targets) and not blocked_scopes(state, ["Web Bob"]):
    context = deployed_project_context(root)
    if context:
        candidates.append(context)
```
- ✅ Fallback only triggered when no other candidates exist
- ✅ Respects explicit Web Bob targeting
- ✅ Respects blocking scopes
- ✅ Existing active work takes precedence (checked before this block)

**3. Test coverage for holds:**
- `test_pinned_context_respects_project_global_and_partial_release_holds` - covers all hold/release combinations
- `test_pinned_context_still_respects_maintenance_and_provider_unavailability` - covers MAINTENANCE file and lane states (needs_key, cooldown, budget_exhausted)
- `test_missing_empty_relative_mismatched_and_unreadable_pins_fail_closed` - exhaustive pin validation

**4. Test coverage for precedence:**
- `test_pinned_context_does_not_displace_a_permitted_ongoing_job` - verifies enqueued source job is used when present

**5. Test coverage for parked projects:**
- `test_parked_project_holds_survive_the_permitted_webbob_dispatch` - verifies Barker/Wildflower holds preserved

**6. Test coverage for invalid context:**
- `test_rollback_copy_without_git_evidence_cannot_supply_report_context` - verifies rollback copy without `.git` fails

**7. API-only restriction:**
- `test_pins_do_not_authorize_other_projects_or_tool_workers` - verifies only "Web Bob" and API workers (gemini, minimax) are permitted

**8. Session-freeze honesty:**
- Prompt includes "Do not infer active work, progress or results from deployment metadata"
- Status check `test_pins_are_context_without_an_open_screen_or_a_claim_of_running_work` verifies "waiting to run" and no "running for" language

**9. Validation results:**
- 333 webchat tests passed
- 131 services tests passed
- 96 evals passed (39 parity + 19 asks × 3 scenarios including deployed_checkout)

### No Critical/High Bugs Found

The implementation correctly:
- Requires both deployment pins to match
- Validates .git existence (prevents rollback copies)
- Uses resolve() for symlink-safe comparison
- Does not fabricate source_job_ids
- Properly handles holds, maintenance, provider unavailability
- Preserves parked project holds
- Does not displace permitted ongoing jobs

VERDICT: PASS
