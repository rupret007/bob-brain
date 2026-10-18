# Round 9 council context (Cursor lane)

Baseline: R18 final SHA `0af1a5c` / code `9af6e24`.

Changes this round (lowest R18 scores first):
- Self-improve: `plain_status` on `/api/panel`; tick runs webchat + failover + services tests; Settings shows short status not wall of text.
- Live dashboard ADDED 02:03: `public_live_ops` exports `service_screen_count` for Pages parity with Jobs tab.
- Music: hook-only coach path ($0, no MiniMax music API).
- Mobile formatting: inline `code` contrast in assistant bubbles.

Diff excerpt in `/tmp/r9-council.diff` (full patch staged for commit).

Ask council: Ship, Defer, or Reject? Focus on drill isolation, dashboard secrets, self-improve tick cost on mini.
