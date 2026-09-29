# Web Bob failover: enhance + prove (Codex job)
Scope: conductor/webchat/ provider routing only. Keep 127.0.0.1 bind, password, confirm cards, hard rules. Never merge/undraft/force-push; no texts/emails.
Enhance:
1. Classify failures per provider: not-logged-in, rate/usage limit, timeout, non-zero exit, empty/garbage output, network. Each gets a clear reason shown in chat ("Codex hit its limit, switched to Cursor").
2. Order Codex -> Cursor (--trust) -> Gemini API -> MiniMax API (respect $48 cap via script-tracked spend). Claude only if Jeff explicitly picks it.
3. Per-provider timeouts, closed stdin, kill whole process group on timeout/Stop.
4. Circuit breaker: after a failure, cool the provider down (e.g. 5m, backoff to 30m); limit errors cool until reset time if parseable. Show lane health in lanes panel.
5. Health probe: cheap background check every ~10m updates provider state; half-open retry after cooldown.
6. Mid-answer failure: retry the same turn on next provider with the same context; never double-run risky actions (confirm-card actions are idempotent/once-only).
7. All providers down: honest message + queue the request, no fake answer.
8. Log every failover decision to logs/webchat-failover.log (JSON lines).
Test (must actually run, not just unit mocks):
- Unit tests with fake providers for every failure class, breaker timing, all-down, mid-answer.
- Live drills against the running server via curl: force-fail Codex (env/flag like BOB_WEBCHAT_FORCE_FAIL=codex), confirm Cursor answers; force-fail codex+cursor, confirm Gemini; all forced down, confirm honest error; recovery after cooldown returns to Codex; Stop kills the child.
- Normal memory question + "merge #158" refusal still pass.
Restart svc-webchat after, verify 127.0.0.1:8787 only.
Commit on a draft branch; write reviews/WEBCHAT-FAILOVER-RESULT.md with a PASS/FAIL table, evidence, commit SHA.

## URGENT UPDATE from Jeff (00:22): chat must never say "busy"
Live on phone: "No provider completed a reply. codex: busy with another job; cursor: busy; gemini: busy". Jeff's chat is interactive and has TOP priority:
- Chat calls must NOT be blocked by background job lane locks/semaphores. Use a separate interactive slot per provider (or preempt: background jobs yield), never reject as busy.
- "busy" is not a failure class that ends the chain: fall through Codex -> Cursor -> Gemini API -> MiniMax API; Gemini/MiniMax HTTP APIs have no single-job lock, so they must always be able to answer.
- Add a test: all background lanes held -> chat still gets a reply. Live-verify with jobs running.
- Do this FIRST, restart svc-webchat (screen 67724.svc-webchat; kill the app.py PID then bash conductor/webchat/start.sh), keep .public-origin, verify via https://jeffs-mac-mini.tail758ab4.ts.net.

## Self-assessment (Jeff 00:24): after drills, score failover 1-10 with evidence, fix weakest, re-test; include scorecard in result.

## ADDED 00:29 (Jeff): Architectural review in the self-assessment
Add an "Architecture" score (0-10) to the scorecard, and it must reach at least 8 like the others. Include a short review in the RESULT file covering:
- Component map: webchat server, providers, locks, job lanes, handback, dashboard-updater, watchdog, Tailscale serve.
- Single points of failure and shared state (global locks, lock files, screen-name collisions, one mini).
- Coupling between chat and the job lanes, and whether chat can starve jobs or jobs can starve chat.
- Failure and recovery paths, stale-lock expiry, and restart safety.
- Security boundary: the password, the public ts.net origin, secrets in the repo or logs.
- The top 5 ranked structural fixes. Implement the ones that are safe tonight, and list the rest with an effort estimate.
Keep everything draft-only, with no merges.
