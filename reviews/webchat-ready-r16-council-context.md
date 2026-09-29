# Council context — Web Bob Round 16 (on R13)

**Ship when:** 115+23+59+ tests PASS, parity **48/48**, handback `r16` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill, `iphone-r16` ≥0.75, this RESULT committed.

**R16 deltas:**
1. **Dashboard tap-through:** `dashboard_plain` rows **Top live job**, **Also running**, **More live jobs** include `action: {type: focus_live_job, index}`; Jobs tab cards use `data-live-job-index`; 44pt buttons in `#jobs-dashboard-plain`.
2. **Jobs cards:** Render all `live_screen` jobs (incl. stalled) so focus targets match plain grid indices.
3. **Music:** post-chorus coach parity ($0).
4. **Handback:** `WEBCHAT_HANDBACK_TAG=r16` two rounds inside one tag (R13 pattern).

**Open questions for council:**
- Is “tap to open cards” suffix OK on **More live jobs** value, or only the button aria-label?
- Should **Top live job** be tappable or only Also/More?

**Do not:** merge, force-push, Grok, MiniMax music API, restart webchat mid-council (restart once after gates).
