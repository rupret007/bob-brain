# Round 17 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Design:** `conductor/reviews/WEBCHAT-READY-R17-DESIGN.md`  
**Baseline:** R38 `faec74b` per `WEBCHAT-READY-R38-RESULT.md`

## Delta (code)

1. **Conductor parity:** `parse_ready_round` wired in `app.py` submit path; Start round chip uses READY phrase → `DEFAULT_READY_ROUND_GOAL` confirm card.
2. **Enhancement 1:** `_italic_` / `*em*` in `renderMarkdown` (assistant bubbles).
3. **Failover:** `ORDER` excludes automatic Claude (last-resort only when `preferred_provider=claude`); matches RULES + `test_failover.py`.
4. **Music ($0):** plagal (amen) IV→I coach in `music_notebook.py`.
5. **Inherited:** R38 dashboard `gap_to_nine`, handback isolated drills, voice `.call-you` contrast, 58-case parity eval.

## Gates to vote on

- `python3 conductor/webchat/test_webchat.py` (97)
- `python3 conductor/webchat/test_failover.py` (24)
- `python3 conductor/services/test_services.py` (66)
- `python3 conductor/webchat/bob_parity_eval.py` (58/58)
- `WEBCHAT_HANDBACK_TAG=r17` handback drill ×2
- `live_ready_drill.py` ts.net
- `BOB_WEBCHAT_DRILLS=1 python3 conductor/webchat/e2e_live.py --isolated`
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r17` capture

No Grok. Draft only.
