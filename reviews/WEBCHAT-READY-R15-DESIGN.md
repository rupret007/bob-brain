# Web Bob Round 15 — design note (research-first)

**Baseline:** R21 measured scores (`WEBCHAT-READY-R21-RESULT.md`, SHA `b1f827a`).

**Borrow**
- R14/R15 council: passive `load_live_ops()` + explicit **Refresh** on Models tab (`POST /api/panel/refresh`).
- R21 verified READY ship gate + Jobs/Models `scores_weakest` focus rows (detailed live dashboard ADDED 02:03).
- Apple HIG: 44pt targets, safe-area, chat-first on narrow widths (hide logout ≤430px for ~75% chat height).
- Jeff 02:00 music constraints: LLM coach only ($0); deceptive cadence coaching.

**Reject**
- MiniMax music API / signups; Grok worker; spawning dashboard refresh on every panel read.

**Why (lowest R21 scores first)**
1. Self-improve **9.42** → `next_action` + plain Settings line + Copy install button wired in HTML.
2. Voice **9.65** → full-contrast call + voice transcript CSS.
3. Conductor **9.66** → Refresh dashboard + Help copy for Models/Settings.
4. iPhone design **9.90** but chat ratio **0.759** → slimmer header pill on phone.

**Sources:** `WEBCHAT-READY-R21-RESULT.md`, `ALIGNMENT-DESIGN.md`, web.dev contrast, MDN Web Speech API.
