Status follow-ups such as “Ok great works on all LLMs now?” now give short, natural summaries of observed work. Casual replies omit raw lane names, missing-model placeholders, queue counts and worker inventories; running, waiting, paused and unconfirmed work stay distinct. Detailed evidence remains in saved status observations and explicit diagnostics.

Release tip: `9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7`. This fixes the live replay failure after PR #18; its retained merge `1d72c44` remains in the target branch. The texting consent and private-context paths are unchanged. The existing isolated texting browser harness now uses CSP-compatible locator waits.

Validation: 389 webchat tests, 131 services tests, 99/99 offline parity/replay evals, 2 deployment guard tests, and the isolated texting browser proof all pass. Fresh Gemini and MiniMax review evidence is recorded under `conductor/reviews/TEXTING-LIVE-0810.*`. The guarded deployment requires BOTH_PASS, snapshots rollback to `a777736`, checks texting smoke, and replays all 19 captured turns.

Keep this PR in draft. The regular merge and deployment are authorized; no force-push or notifications.
