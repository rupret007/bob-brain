---
name: Mini paste Working proof
description: >-
  use this when Mini Codex/Claude stress pastes must prove Working/Pursuing —
  require OUT+GOAL for native inject; window-isolated screencapture -l; exclude Bob OCR;
  PARTIAL vs WEAK per R8 research R2
---
# Mini paste Working proof (post-R8 strengthened)

Composer paste alone ≠ Working. Goal: raise PARTIAL → **STRONG** via mid-Working window prove (3–5s).

## Native inject contract (REQUIRED)
R7 exit **133** = SIGTRAP from Swift force-unwrap of missing env:
```bash
export OUT=~/Documents/bob-overnight-inject/harden-stress-rN-<stamp>
export GOAL=$OUT/codex-goal.txt   # or claude-goal.txt
"$OUT/native/inject_chatgpt"      # or inject_claude
```
Without **both** `OUT` and `GOAL` → crash. Accessibility required for CGEvent HID.

## Window-isolated prove (REQUIRED for STRONG)
1. Activate target app (ChatGPT / Claude).
2. Resolve on-screen window id (`CGWindowList` / `ax_dump` helper) — layer 0, owner match.
3. `screencapture -x -l <wid> $OUT/<app>-prove-working.png` — **not** full desktop.
4. OCR that PNG only.
5. **Exclude** any OCR line matching `/bob the bot/i` before scoring (desktop Bob chip ≠ Mini Working).
6. Prove at **3–5s mid-Working** (too late → idle welcome / Goal achieved only).

## Scoring
| Grade | Meaning |
| --- | --- |
| **STRONG** | Window-isolated OCR shows Working for Ns / Pursuing goal (+ composer cleared); no Bob-only match; no idle welcome |
| **PARTIAL** | Native exit0 + Sent as goal and/or Goal achieved, but chip not window-clean STRONG |
| **WEAK** | Paste-with-idle-welcome only, or Bob-OCR false positive, or missing OUT/GOAL crash |

## Done checklist
1. `*-prove-working.png` from `-l` window capture
2. `*-prove-ocr.txt` with Bob lines dropped for score
3. `*-prove-verdict.txt` = STRONG|PARTIAL|WEAK + note
4. Negative: text still in composer + idle welcome = WEAK

## Pair with
bob-codex-queue-inject · gemini-direct-invoke-recipe · minimax-tip-verdict-contract


## R9 escalate — Unknown skill: goal (2026-09-25 ~03:27 CT)
ChatGPT after-send OCR showed `Unknown skill: goal` when the paste started with `/goal ...`.
Sidebar recorded the title but **Working / Sent as goal never appeared**.

### Contract update
1. Prefer goal body **without** leading `/goal` slash-skill if the live Codex build treats it as unknown.
2. Alternate: use the Codex UI control that historically yielded **Sent as goal** (R8 evidence), then paste body.
3. Still require OUT+GOAL env for native Mach-O; window-isolated prove at 3-5s; exclude Bob OCR.
4. Score STRONG only on window OCR Working for Ns / Pursuing goal — never on goal-text echoing "Working|Pursuing".

## R13 escalate — ChatGPT click bounds + OCR anti-echo (2026-09-25 ~03:40 CT)
Measured hole: Codex stayed WEAK/idle across R9–R13. R13 root cause found:
default `inject_chatgpt` composer click `(1280,1320)` is **outside** live ChatGPT
window bounds `X=20,Y=30,W=1400,H=950` (hits Claude/Cursor stack). Paste/send
never reliably lands in Goal composer above the terminal pane.

### Contract update
1. **Resolve bounds first** via `CGWindowList` layer-0 ChatGPT wid; never hardcode
   (1280,1320). Composer ≈ center-x of window, **above terminal** (~y = winY+winH-210
   on current Mini layout); send ≈ right edge of that strip.
2. Prove with `screencapture -x -l <wid>` using that wid — full-desktop OCR false-mixes Claude.
3. **OCR scoring (strict)**:
   - STRONG only: `Working for \d` / `Pursuing goal` (window-isolated), composer cleared, no idle welcome.
   - Do **not** treat `working-chip` title or goal body `STATUS: Working` as chip evidence.
   - Idle welcome (`What should we build`) + text still in composer = WEAK even if sidebar title updated.
4. `/goal` prefix still optional (R9 Unknown skill); coord-correct body-without-`/goal` first.
5. If same tip fails twice → escalate this skill (done R13); do not vanity-commit dashboard.
6. Ship `native/inject_chatgpt` rebuild with bounds-aware clicks when next Mini round opens;
   keep OUT+GOAL env contract.


## R18 escalate — bounds-aware inject shipped + STRONG (2026-09-25 ~03:49 CT)
Root cause confirmed: hardcoded (1280,1320) outside ChatGPT bounds (X=20 Y=30 W=1400 H=950);
click hit Claude overlap (Claude X≈1277).

### Shipped inject contract
1. `CGWindowList` resolve layer-0 ChatGPT wid + bounds every run.
2. Composer: `x=win.x+min(0.42*w,550)`, `y=win.y+h-280` (left of Claude overlap).
3. Send: in-window click at composer+(320,0) capped `< win.x+w-200` PLUS Cmd+Return/Return.
   Never click near right edge (≥~1277) — steals focus to Claude.
4. Screenshots via `screencapture -l <wid>` only.
5. OCR anti-echo: drop goal-title lines BUT **never drop** lines matching `Working for \d` /
   `Pursuing goal` / `Sent as goal` (R18 false PARTIAL when chip shared a sidebar title line).
6. OUT+GOAL env still required.

### Evidence R18
- Paste landed in composer (chatgpt-03-pasted.png OCR).
- Prove OCR: `Working for 5s` + agent text locating 78b6301 → **STRONG**.
