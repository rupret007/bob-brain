---
name: AI R&D reuse hunt
description: >-
  use this when Jeff or Bob needs existing OSS, GitHub examples, or
  orchestrators for a capability (Codex goals, Telegram, Logic, dashboards,
  conductors) instead of writing from scratch — reuse first; judge how others
  wrote it and whether it actually works well.
---
# AI R&D reuse hunt

## When
Any new capability, sticky integration, or “we could build this” moment. Default bias: **search before generate**.

## Steps
1. **Name the need** — capability, constraints, must-nots (secrets, auto-send, ToS), success look.
2. **Search Jeff’s own repos first** — reuse before rewrite.
3. **Search outside** — GitHub / web / plugins for battle-tested code (recency, stars/forks as weak signals, clear license, real docs).
4. **Read how they wrote it** — architecture, API surface, error handling, tests, config story. Prefer clear small cores over giant frameworks.
5. **Check whether it works well** — evidence over vibes:
   - recent commits / issues that get answers
   - CI or tests that actually run
   - real usage notes (README “works on…”, release notes, independent writeups)
   - try a smoke path when cheap (install, `--help`, doctor, one happy-path call)
   - note known failure modes
6. **Score top candidates** (short table):
   - fit to the need
   - quality of the writing (clarity, structure)
   - proof it works (tests/CI/smoke/field reports)
   - license / ToS safety
   - maintenance signal
   - integration cost on this stack
   - token savings vs writing new
7. **Pick one** — recommend adopt / fork / steal-pattern / skip. Prefer pattern theft over heavy deps when lighter. Skip pretty-but-broken.
8. **Deliver** — memo with links + what works / what doesn’t + next wire step. Only implement when clearly safe and in scope.
9. **Quiet otherwise** — if nothing beats current approach, say so in one line or stay quiet on routine runs.

## Anti-patterns
- Reimplementing a solved conductor/orchestrator/dashboard auth pattern
- Adopting high-star code that fails smoke or has dead maintainers
- Pulling unmaintained or sketchy-license code into Cisco/customer paths
- Letting a hunt block shipping a thin working path

## Output shape
Short prose + optional top-3 list with **works?** call. No essay.
