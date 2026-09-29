You are Codex on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057
Branch: draft/webbob-integrate-2057 @ 61ad058 (PR #17 draft). Drafts only. No deploy/merge/undraft/force-push. No secrets. Do NOT restart live services. Do NOT recreate STOP-WEBBOB. Never use Grok/xAI.

CONTEXT: Three live deploy attempts of this integrate SHA family (replyq + apiworkers + lanes) all rolled back. Live tip remains dff84e3. See conductor/reviews/WEBBOB-INTEGRATE-FAIL-0927.md and WEBBOB-INTEGRATE-RUBRIC-0927-attempt3.json.

Attempt 3 failure: status observation — running counts changed from 1→5 around a reply reporting 3; gate did not preserve the exact snapshot used to render that reply. Outstanding fix from rubric: "Capture the timestamped observation used by each status reply and validate against that evidence during worker startup. Keep receipt and observed-worker checks strict."

GOAL this lane (code only, no live deploy):
1. Implement durable per-reply status observation snapshots (timestamped) used by status/worker replies so live validation can compare like-for-like.
2. Fix any related honesty bugs that caused attempt1/2 failures if still present (unbounded lane greeting overflow; verbose completion summaries — keep concise + linked).
3. Full webchat + services tests + eval suite must pass.
4. Commit + regular-push to brain draft/webbob-integrate-2057; update/open draft PR only if needed (stay draft).
5. Write ~/Documents/bob-overnight-inject/conductor/reviews/INTEGRATE-FIXED-2143.md with tip SHA, test counts, and READY or STILL-FAIL. Do not claim LIVE PASS. Do not notify Jeff.
